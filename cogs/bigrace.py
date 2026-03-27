import asyncio
import datetime
import os
import random

import discord
from discord.ext import commands, tasks

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from database import (
    get_user_monies, get_user_carats, update_carats,
    get_race_channel, set_race_channel, get_all_race_configs,
    is_enrolled, toggle_enrollment, get_enrolled_users,
)
from helpers import info_embed, error_embed
from cogs.horserace import (
    simulate_race, estimate_win_rates, to_fractional_odds, _best_fraction,
    format_race_progress,
    HORSE_NAMES, HORSE_IMAGES,
)

_PT = ZoneInfo("America/Los_Angeles")
_CARAT_IMAGE = os.path.join(os.path.dirname(__file__), "..", "data", "carat.png")


class BigRace(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_big_races: dict = {}  # guild_id -> race_state
        self.daily_race.start()

    def cog_unload(self):
        self.daily_race.cancel()

    # ------------------------------------------------------------------ #
    # Scheduler                                                           #
    # ------------------------------------------------------------------ #

    @tasks.loop(time=datetime.time(21, 0, tzinfo=_PT))
    async def daily_race(self):
        rows = get_all_race_configs()
        for guild_id, channel_id in rows:
            asyncio.create_task(
                self._run_big_race(int(guild_id), int(channel_id))
            )

    @daily_race.before_loop
    async def before_daily_race(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------ #
    # Commands                                                            #
    # ------------------------------------------------------------------ #

    @commands.command(name="setracechannel", help="Set the channel for the daily big race")
    @commands.has_permissions(manage_guild=True)
    async def set_race_channel_cmd(self, ctx, channel: discord.TextChannel = None):
        if channel is None:
            channel_id = get_race_channel(str(ctx.guild.id))
            if channel_id is None:
                await ctx.send(embed=info_embed(
                    "📍 Big Race Channel",
                    "No big race channel configured. Use `!setracechannel #channel`.",
                    discord.Color.orange(),
                ))
            else:
                ch = self.bot.get_channel(int(channel_id))
                name = f"<#{channel_id}>" if ch else f"ID {channel_id} (channel not found)"
                await ctx.send(embed=info_embed(
                    "📍 Big Race Channel",
                    f"Current big race channel: {name}",
                    discord.Color.blue(),
                ))
            return

        set_race_channel(str(ctx.guild.id), str(channel.id))
        await ctx.send(embed=info_embed(
            "✅ Big Race Channel Set",
            f"Daily big race will be announced in {channel.mention}.",
            discord.Color.green(),
        ))

    @commands.command(name="testbigrace", help="(Admin) Trigger a big race in the current channel immediately")
    @commands.has_permissions(manage_guild=True)
    async def test_big_race(self, ctx):
        import asyncio
        asyncio.create_task(self._run_big_race(ctx.guild.id, ctx.channel.id))

    @commands.command(name="racenotify", help="Toggle daily big race notifications")
    async def race_notify(self, ctx):
        enrolled = toggle_enrollment(str(ctx.author.id), str(ctx.guild.id))
        if enrolled:
            await ctx.send(embed=info_embed(
                "✅ You're In!",
                "You'll be pinged before the daily big race at 9pm PT.",
                discord.Color.green(),
            ))
        else:
            await ctx.send(embed=info_embed(
                "🔕 Removed",
                "You won't be pinged for the daily big race.",
                discord.Color.greyple(),
            ))

    @commands.command(name="racebetbig", help="Bet carats on the big race: !racebetbig <number> <amount>")
    async def race_bet_big(self, ctx, horse_number: int, amount: int):
        guild_id = ctx.guild.id

        if guild_id not in self.active_big_races:
            await ctx.send(embed=error_embed("No big race is running right now!"))
            return

        race = self.active_big_races[guild_id]
        if not race["betting_open"]:
            await ctx.send(embed=error_embed("Betting is closed — the race has already begun!"))
            return

        horses = race["horses"]
        horse = next((h for h in horses if h["number"] == horse_number), None)
        if horse is None:
            valid = ", ".join(str(h["number"]) for h in horses)
            await ctx.send(embed=error_embed(f"Invalid horse number. Valid: {valid}"))
            return

        if amount <= 0:
            await ctx.send(embed=error_embed("Bet amount must be positive."))
            return

        user_id = ctx.author.id
        for h in horses:
            if user_id in h["bets"]:
                await ctx.send(embed=error_embed("You already placed a bet in this race!"))
                return

        # Ensure the user row exists before reading carats
        get_user_monies(user_id, guild_id)
        carats = get_user_carats(user_id, guild_id)
        if carats < amount:
            await ctx.send(embed=error_embed(
                f"Insufficient carats! You have **{carats}** carats."
            ))
            return

        update_carats(user_id, guild_id, carats - amount)
        horse["bets"][user_id] = amount

        n, d = _best_fraction(race["win_rates"][horse_number])
        potential_payout = amount + int(amount * n / d)

        await ctx.send(embed=info_embed(
            "✅ Bet Placed",
            f"{ctx.author.mention} bet **{amount}** carats on **#{horse_number} {horse['name']}**!\n"
            f"Potential payout: **{potential_payout}** carats",
            discord.Color.green(),
        ))

    # ------------------------------------------------------------------ #
    # Race runner                                                         #
    # ------------------------------------------------------------------ #

    async def _run_big_race(self, guild_id: int, channel_id: int):
        # Guard: skip if a regular race is already active in this guild
        horserace_cog = self.bot.cogs.get("HorseRace")
        if horserace_cog and guild_id in horserace_cog.active_races:
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return
        try:
            await channel.send("test", delete_after=0)
        except discord.Forbidden:
            return
        except Exception:
            pass

        # Ping enrolled users
        enrolled_ids = get_enrolled_users(str(guild_id))
        guild = self.bot.get_guild(guild_id)
        mentions = []
        if guild:
            for uid in enrolled_ids:
                member = guild.get_member(int(uid))
                if member:
                    mentions.append(member.mention)
        if mentions:
            await channel.send(
                " ".join(mentions) + "\n**The Daily Big Race is starting in 5 minutes — place your bets!**"
            )

        # Build horses
        num_horses = random.randint(4, 6)
        names = random.sample(HORSE_NAMES, num_horses)
        horses = [
            {
                "number": i,
                "name": name,
                "weight": random.randint(4, 9),
                "stamina": random.randint(4, 9),
                "consistency": random.randint(3, 9),
                "bets": {},
            }
            for i, name in enumerate(names, start=1)
        ]

        win_rates = await asyncio.to_thread(estimate_win_rates, horses)

        self.active_big_races[guild_id] = {
            "horses": horses,
            "channel_id": channel_id,
            "betting_open": True,
            "win_rates": win_rates,
        }

        try:
            # Build and send betting embed
            favourite_num = max(win_rates, key=win_rates.get)
            lines = []
            for h in horses:
                rate = win_rates[h["number"]]
                frac = to_fractional_odds(rate)
                raw = (1 - rate) / rate if rate > 0 else 999
                if h["number"] == favourite_num:
                    label = "⭐ Favourite"
                elif raw < 4.0:
                    label = "Contender"
                elif raw < 10.0:
                    label = "Longshot"
                else:
                    label = "Outsider"
                lines.append(
                    f"**#{h['number']} {h['name']}** — {label}\n"
                    f"> 🔥\u2003{h['weight']}\u2003\u2003🔋\u2003{h['stamina']}\u2003\u2003🎯\u2003{h['consistency']}\u2003\u2003Odds: **{frac}**"
                )

            horse_field_value = "\n".join(lines)

            def _build_betting_embed(countdown: str) -> discord.Embed:
                e = discord.Embed(
                    title="🏇 Daily Big Race!",
                    description=f"Place your bets now! Use `!racebetbig <number> <amount>`.\n**Betting closes in {countdown}.**",
                    color=discord.Color.purple(),
                )
                e.add_field(
                    name="🔥 Weight  🔋 Stamina  🎯 Consistency",
                    value=horse_field_value,
                    inline=False,
                )
                e.set_footer(text="Odds are fixed at race start. Bets use carats.")
                e.set_thumbnail(url="attachment://carat.png")
                return e

            carat_file = discord.File(_CARAT_IMAGE, filename="carat.png")
            betting_msg = await channel.send(file=carat_file, embed=_build_betting_embed("300 seconds"))

            # Live countdown — edit every 10 seconds
            betting_window = 300  # 5 minutes
            interval = 10
            for elapsed in range(interval, betting_window, interval):
                await asyncio.sleep(interval)
                remaining = betting_window - elapsed
                await betting_msg.edit(embed=_build_betting_embed(f"{remaining} seconds"))
            await asyncio.sleep(interval)  # final interval to reach 0

            race = self.active_big_races.get(guild_id)
            if race is None:
                return
            race["betting_open"] = False
            horses = race["horses"]

            # Simulate and animate
            finish_order, snapshots = simulate_race(horses)
            initial_positions = {h["number"]: 0.0 for h in horses}
            race_msg = await channel.send(
                format_race_progress(horses, initial_positions, "And they're off!")
            )
            checkpoints = [(round(x * 0.1, 1), f"{x * 10}% Complete") for x in range(1, 10)]
            for milestone, label in checkpoints:
                await asyncio.sleep(1)
                positions = snapshots.get(milestone, initial_positions)
                await race_msg.edit(content=format_race_progress(horses, positions, label))
            await asyncio.sleep(1)

            # Payouts
            winner_num = finish_order[0]
            winner = next(h for h in horses if h["number"] == winner_num)

            all_bets = {}
            for h in horses:
                for uid, amt in h["bets"].items():
                    all_bets[uid] = (h["number"], amt)

            winning_bets = {uid: amt for uid, (num, amt) in all_bets.items() if num == winner_num}

            race_win_rates = race["win_rates"]
            n, d = _best_fraction(race_win_rates[winner_num])
            odds_multiplier = n / d
            frac_str = to_fractional_odds(race_win_rates[winner_num])

            medals = ["🥇", "🥈", "🥉"]
            podium_lines = []
            for i, num in enumerate(finish_order[:3]):
                h = next(x for x in horses if x["number"] == num)
                medal = medals[i] if i < len(medals) else f"#{i + 1}"
                podium_lines.append(f"{medal} **#{num} {h['name']}**")

            payout_lines = []
            if not all_bets:
                payout_lines.append("No bets were placed — just a fun race!")
            elif not winning_bets:
                payout_lines.append(f"No one bet on **#{winner_num} {winner['name']}** — no payouts.")
            else:
                guild_obj = self.bot.get_guild(guild_id)
                for uid, amt in winning_bets.items():
                    profit = int(amt * odds_multiplier)
                    payout = amt + profit
                    carats = get_user_carats(uid, guild_id)
                    update_carats(uid, guild_id, carats + payout)
                    if guild_obj:
                        member = guild_obj.get_member(int(uid))
                        display = member.display_name if member else f"<@{uid}>"
                    else:
                        display = f"<@{uid}>"
                    payout_lines.append(f"💰 {display}: **+{profit}** carats (bet {amt} @ {frac_str})")

            result_embed = discord.Embed(
                title=f"🏁 {winner['name']} wins the Daily Big Race!",
                color=discord.Color.purple(),
            )
            result_embed.add_field(name="Podium", value="\n".join(podium_lines), inline=False)
            result_embed.add_field(name="Payouts", value="\n".join(payout_lines), inline=False)
            winner_image = HORSE_IMAGES.get(winner["name"])
            if winner_image:
                result_embed.set_image(url=winner_image)

            # Clear the progress bar message, then send result as a fresh message
            # (discord.File must be a new instance — cannot reuse the one from the betting embed)
            await race_msg.edit(content="✅ Race complete! Results below.")
            carat_file2 = discord.File(_CARAT_IMAGE, filename="carat.png")
            result_embed.set_thumbnail(url="attachment://carat.png")
            await channel.send(file=carat_file2, embed=result_embed)
        finally:
            self.active_big_races.pop(guild_id, None)


async def setup(bot):
    await bot.add_cog(BigRace(bot))
