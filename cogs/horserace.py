import asyncio
import random

import discord
from discord.ext import commands

from database import get_user_points, update_points
from helpers import info_embed, error_embed

HORSE_NAMES = [
    "Special Week", "Silence Suzuka", "Tokai Teio", "Mejiro McQueen",
    "Gold Ship", "Oguri Cap", "Vodka", "Daiwa Scarlet",
    "Seiun Sky", "El Condor Pasa", "Grass Wonder", "Haru Urara",
    "Nice Nature", "Narita Brian", "Biwa Hayahide", "Sakura Bakushin O",
    "Tamamo Cross", "Super Creek", "Air Groove", "Symboli Rudolf",
]


def build_progress_bar(progress: float, width: int = 20) -> str:
    filled = int(progress * width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def simulate_race(horses: list) -> tuple:
    """Simulate 40 ticks. Returns (finish_order, snapshots).

    snapshots: {tick: {horse_num: float}} captured at ticks 10, 20, 30.
    finish_order: list of horse numbers in finishing order.
    """
    positions = {h["number"]: 0.0 for h in horses}
    finish_order = []
    finished = set()
    snapshots = {}

    for tick in range(1, 41):
        for h in horses:
            if h["number"] in finished:
                continue
            speed = (h["weight"] / 20.0) + random.uniform(0, 0.08)
            positions[h["number"]] = min(1.0, positions[h["number"]] + speed)
            if positions[h["number"]] >= 1.0:
                finished.add(h["number"])
                finish_order.append(h["number"])

        if tick in (10, 20, 30):
            snapshots[tick] = dict(positions)

    # Any stragglers not yet in finish_order
    for h in horses:
        if h["number"] not in finished:
            finish_order.append(h["number"])

    return finish_order, snapshots


def format_race_progress(horses: list, positions: dict, label: str) -> str:
    lines = [f"**🏇 Race in Progress — {label}**\n"]
    for h in horses:
        num = h["number"]
        prog = positions.get(num, 0.0)
        bar = build_progress_bar(prog)
        pct = int(prog * 100)
        lines.append(f"`#{num}` {h['name']} {bar} {pct}%")
    return "\n".join(lines)


class HorseRace(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_races: dict = {}  # guild_id -> race_state

    @commands.command(name="race", help="Start a horse race with a 60-second betting window")
    async def start_race(self, ctx):
        guild_id = ctx.guild.id

        if guild_id in self.active_races:
            await ctx.send(embed=error_embed(
                "A race is already running! Use `!racebet <number> <amount>` to place your bet."
            ))
            return

        num_horses = random.randint(4, 6)
        names = random.sample(HORSE_NAMES, num_horses)

        horses = []
        for i, name in enumerate(names, start=1):
            horses.append({
                "number": i,
                "name": name,
                "weight": random.randint(1, 10),
                "bets": {},  # user_id -> amount
            })

        self.active_races[guild_id] = {
            "horses": horses,
            "channel_id": ctx.channel.id,
            "betting_open": True,
        }

        total_weight = sum(h["weight"] for h in horses)
        lines = []
        for h in horses:
            odds = total_weight / h["weight"]
            lines.append(f"**#{h['number']}** {h['name']} — Odds: **{odds:.2f}x**")

        embed = discord.Embed(
            title="🏇 Horse Race Starting!",
            description=(
                "Place your bets now! Use `!racebet <number> <amount>`.\n"
                "**Betting closes in 60 seconds.**"
            ),
            color=discord.Color.gold(),
        )
        embed.add_field(name="Horses", value="\n".join(lines), inline=False)
        embed.set_footer(text="Parimutuel betting — payout depends on total bets on the winner.")

        await ctx.send(embed=embed)
        await asyncio.sleep(60)
        await self._run_race(ctx, guild_id)

    @commands.command(name="racebet", help="Bet on a horse: !racebet <horse_number> <amount>")
    async def race_bet(self, ctx, horse_number: int, amount: int):
        guild_id = ctx.guild.id

        if guild_id not in self.active_races:
            await ctx.send(embed=error_embed("No race is running! Start one with `!race`."))
            return

        race = self.active_races[guild_id]

        if not race["betting_open"]:
            await ctx.send(embed=error_embed("Betting is closed — the race has already begun!"))
            return

        horses = race["horses"]
        horse = next((h for h in horses if h["number"] == horse_number), None)
        if horse is None:
            valid = ", ".join(str(h["number"]) for h in horses)
            await ctx.send(embed=error_embed(f"Invalid horse number. Valid choices: {valid}"))
            return

        if amount <= 0:
            await ctx.send(embed=error_embed("Bet amount must be positive."))
            return

        user_id = ctx.author.id

        for h in horses:
            if user_id in h["bets"]:
                await ctx.send(embed=error_embed("You already placed a bet in this race!"))
                return

        user_points = get_user_points(user_id, guild_id)
        if user_points < amount:
            await ctx.send(embed=error_embed(
                f"Insufficient points! You have **{user_points}** points."
            ))
            return

        update_points(user_id, guild_id, user_points - amount)
        horse["bets"][user_id] = amount

        total_weight = sum(h["weight"] for h in horses)
        odds = total_weight / horse["weight"]

        embed = info_embed(
            "✅ Bet Placed",
            f"{ctx.author.mention} bet **{amount}** points on "
            f"**#{horse_number} {horse['name']}**!\n"
            f"Current odds: **{odds:.2f}x**",
            discord.Color.green(),
        )
        await ctx.send(embed=embed)

    async def _run_race(self, ctx, guild_id: int):
        race = self.active_races.get(guild_id)
        if race is None:
            return

        race["betting_open"] = False
        horses = race["horses"]
        channel = self.bot.get_channel(race["channel_id"])
        if channel is None:
            del self.active_races[guild_id]
            return

        finish_order, snapshots = simulate_race(horses)

        # Send initial message at the gates
        initial_positions = {h["number"]: 0.0 for h in horses}
        race_msg = await channel.send(
            format_race_progress(horses, initial_positions, "And they're off!")
        )

        # Three checkpoint edits
        checkpoints = [(10, "25% Complete"), (20, "50% Complete"), (30, "75% Complete")]
        for tick, label in checkpoints:
            await asyncio.sleep(4)
            positions = snapshots.get(tick, initial_positions)
            await race_msg.edit(content=format_race_progress(horses, positions, label))

        await asyncio.sleep(4)

        # Build final results
        winner_num = finish_order[0]
        winner = next(h for h in horses if h["number"] == winner_num)

        # Collect all bets
        all_bets = {}  # user_id -> (horse_num, amount)
        for h in horses:
            for uid, amt in h["bets"].items():
                all_bets[uid] = (h["number"], amt)

        total_pool = sum(amt for _, amt in all_bets.values())
        winning_bets = {uid: amt for uid, (num, amt) in all_bets.items() if num == winner_num}
        winning_total = sum(winning_bets.values())

        # Podium
        medals = ["🥇", "🥈", "🥉"]
        podium_lines = []
        for i, num in enumerate(finish_order[:3]):
            h = next(x for x in horses if x["number"] == num)
            medal = medals[i] if i < 3 else f"#{i + 1}"
            podium_lines.append(f"{medal} **#{num} {h['name']}**")

        # Payouts
        payout_lines = []
        if total_pool == 0:
            payout_lines.append("No bets were placed — just a fun race!")
        elif winning_total == 0:
            for uid, (_, amt) in all_bets.items():
                pts = get_user_points(uid, guild_id)
                update_points(uid, guild_id, pts + amt)
            payout_lines.append(
                f"No one bet on **#{winner_num} {winner['name']}** — all bets refunded!"
            )
        else:
            for uid, amt in winning_bets.items():
                payout = int((amt / winning_total) * total_pool)
                pts = get_user_points(uid, guild_id)
                update_points(uid, guild_id, pts + payout)
                try:
                    member = await ctx.guild.fetch_member(uid)
                    display = member.display_name
                except Exception:
                    display = f"<@{uid}>"
                payout_lines.append(f"💰 {display}: **+{payout}** points (bet {amt})")

        final_text = (
            f"**🏁 Race Finished!**\n\n"
            f"**Podium:**\n" + "\n".join(podium_lines) +
            f"\n\n**Payouts:**\n" + "\n".join(payout_lines)
        )
        await race_msg.edit(content=final_text)

        del self.active_races[guild_id]


async def setup(bot):
    await bot.add_cog(HorseRace(bot))
