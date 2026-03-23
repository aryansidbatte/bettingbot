import asyncio
import json
import os
import random

import discord
from discord.ext import commands

from database import get_user_points, update_points
from helpers import info_embed, error_embed

_data_path = os.path.join(os.path.dirname(__file__), "..", "data", "horses.json")
with open(_data_path) as _f:
    _horses = json.load(_f)

HORSE_NAMES = _horses["names"]
_BASE = _horses["base_url"]
HORSE_IMAGES = {name: f"{_BASE}/{path}" for name, path in _horses["images"].items()}


def build_progress_bar(progress: float, width: int = 20) -> str:
    filled = int(progress * width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def simulate_race(horses: list) -> tuple:
    """Simulate up to 200 ticks. Returns (finish_order, snapshots).

    Each horse has:
      - weight (1-10): sets base speed
      - stamina (1-10): higher = less speed decay as position increases
      - consistency (1-10): higher = tighter noise range per tick

    snapshots: {0.1, 0.2, ..., 0.9} captured when the leader first crosses
    each milestone. finish_order: list of horse numbers in finishing order.
    """
    positions = {h["number"]: 0.0 for h in horses}
    finish_order = []
    finished = set()
    snapshots = {}
    pending_milestones = [round(x * 0.1, 1) for x in range(1, 10)]  # 0.1 … 0.9

    for tick in range(1, 201):
        for h in horses:
            if h["number"] in finished:
                continue
            pos = positions[h["number"]]
            # All horses share a base speed; weight gives a small ±adjustment
            base = 0.055 + (h["weight"] - 5) * 0.0005
            # Stamina: speed decays as position increases; high stamina = less decay
            stamina_factor = 1.0 - (pos * (1.0 - h["stamina"] / 10.0) * 0.3)
            # Consistency: centered noise — high = tight/predictable, low = wide/unpredictable
            # Centered at 0 so consistency only affects variance, not average speed
            half_range = 0.018 + (10 - h["consistency"]) * 0.003
            noise = random.uniform(-half_range, half_range)
            speed = max(0.001, (base * stamina_factor) + noise)
            positions[h["number"]] = min(1.0, pos + speed)
            if positions[h["number"]] >= 1.0:
                finished.add(h["number"])
                finish_order.append(h["number"])

        if pending_milestones:
            leader_pos = max(positions.values())
            while pending_milestones and leader_pos >= pending_milestones[0]:
                snapshots[pending_milestones.pop(0)] = dict(positions)

        if len(finished) == len(horses):
            break

    for h in horses:
        if h["number"] not in finished:
            finish_order.append(h["number"])

    return finish_order, snapshots


# Standard racing fractional odds, ordered from shortest to longest
_STANDARD_FRACTIONS = [
    (1, 4), (2, 7), (1, 3), (2, 5), (1, 2), (4, 7), (8, 13), (4, 6),
    (8, 11), (4, 5), (5, 6), (10, 11), (1, 1),  # evens
    (11, 10), (6, 5), (5, 4), (11, 8), (6, 4), (13, 8), (7, 4), (15, 8),
    (2, 1), (85, 40), (9, 4), (5, 2), (11, 4), (3, 1), (100, 30),
    (7, 2), (4, 1), (9, 2), (5, 1), (11, 2), (6, 1), (13, 2), (7, 1),
    (15, 2), (8, 1), (9, 1), (10, 1), (12, 1), (14, 1), (16, 1), (20, 1),
    (25, 1), (33, 1), (50, 1), (66, 1), (100, 1),
]


def to_fractional_odds(win_rate: float) -> str:
    """Convert a win rate (0-1) to the nearest standard fractional odds string."""
    if win_rate <= 0:
        return "100-1"
    raw = (1 - win_rate) / win_rate  # e.g. 0.33 → 2.03
    best = min(_STANDARD_FRACTIONS, key=lambda f: abs(f[0] / f[1] - raw))
    return f"{best[0]}-{best[1]}"


def estimate_win_rates(horses: list, trials: int = 300) -> dict:
    """Run the simulation `trials` times. Returns {horse_number: win_rate}.

    Uses Laplace smoothing so no horse ever gets a 0% or 100% rate,
    keeping displayed odds in a realistic range.
    """
    wins = {h["number"]: 0 for h in horses}
    for _ in range(trials):
        finish_order, _ = simulate_race(horses)
        wins[finish_order[0]] += 1
    n = len(horses)
    return {
        num: (wins[num] + 1) / (trials + n)
        for num in wins
    }


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

    @commands.command(name="race", help="Start a horse race with a 10-second betting window")
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
                "weight": random.randint(4, 9),
                "stamina": random.randint(4, 9),
                "consistency": random.randint(3, 9),
                "bets": {},
            })

        self.active_races[guild_id] = {
            "horses": horses,
            "channel_id": ctx.channel.id,
            "betting_open": True,
        }

        win_rates = estimate_win_rates(horses)
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
                f"**#{h['number']}** {h['name']} "
                f"— 🔥{h['weight']} 🔋{h['stamina']} 🎯{h['consistency']} "
                f"— Odds: **{frac}** ({label})"
            )

        embed = discord.Embed(
            title="🏇 Horse Race Starting!",
            description=(
                "Place your bets now! Use `!racebet <number> <amount>`.\n"
                "**Betting closes in 10 seconds.**"
            ),
            color=discord.Color.gold(),
        )
        embed.add_field(name="Horses (🔥 Weight  🔋 Stamina  🎯 Consistency)", value="\n".join(lines), inline=False)
        embed.set_footer(text="Odds are estimates only — actual payout is parimutuel.")

        await ctx.send(embed=embed)
        await asyncio.sleep(10)
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

        win_rates = estimate_win_rates(horses)
        frac = to_fractional_odds(win_rates[horse_number])

        embed = info_embed(
            "✅ Bet Placed",
            f"{ctx.author.mention} bet **{amount}** points on "
            f"**#{horse_number} {horse['name']}**!\n"
            f"Morning line odds: **{frac}**",
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

        winner_num = finish_order[0]
        winner = next(h for h in horses if h["number"] == winner_num)

        all_bets = {}
        for h in horses:
            for uid, amt in h["bets"].items():
                all_bets[uid] = (h["number"], amt)

        total_pool = sum(amt for _, amt in all_bets.values())
        winning_bets = {uid: amt for uid, (num, amt) in all_bets.items() if num == winner_num}
        winning_total = sum(winning_bets.values())

        medals = ["🥇", "🥈", "🥉"]
        podium_lines = []
        for i, num in enumerate(finish_order[:3]):
            h = next(x for x in horses if x["number"] == num)
            medal = medals[i] if i < 3 else f"#{i + 1}"
            podium_lines.append(f"{medal} **#{num} {h['name']}**")

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

        embed = discord.Embed(
            title=f"🏁 {winner['name']} wins the race!",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Podium", value="\n".join(podium_lines), inline=False)
        embed.add_field(name="Payouts", value="\n".join(payout_lines), inline=False)
        winner_image = HORSE_IMAGES.get(winner["name"])
        if winner_image:
            embed.set_image(url=winner_image)
        await race_msg.edit(content="", embed=embed)

        del self.active_races[guild_id]


async def setup(bot):
    await bot.add_cog(HorseRace(bot))
