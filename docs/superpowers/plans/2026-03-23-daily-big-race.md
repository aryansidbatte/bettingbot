# Daily Big Race Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a scheduled daily horse race at 9pm PT that uses a separate "carats" currency, with admin-configured channels and per-user notification opt-in, and rename "points" to "monies" throughout.

**Architecture:** Database layer first (schema changes, new helpers), then update existing cogs to use new helpers, then create the new `bigrace` cog with its scheduler and commands, then wire everything together in `main.py`. Each task is independently testable and committable.

**Tech Stack:** Python 3.9+, discord.py 2.6.4, SQLite (via module-level connection), `discord.ext.tasks`, `zoneinfo` (stdlib), pytest

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `database.py` | Modify | DB path, rename `points`→`monies`, add `carats`, new tables, new helpers |
| `tests/conftest.py` | Modify | Update in-memory schema to match new `users` table |
| `tests/test_database.py` | Modify | Rename test classes/assertions, add new helper tests |
| `cogs/economy.py` | Modify | Use `get_user_monies`/`update_monies`, `add_daily_reward`, display "monies" |
| `cogs/betting.py` | Modify | Use `get_user_monies`/`update_monies`, display "monies" |
| `cogs/horserace.py` | Modify | Use `get_user_monies`/`update_monies`, display "monies" |
| `cogs/bigrace.py` | Create | `!setracechannel`, `!racenotify`, `!racebetbig`, scheduler, `_run_big_race` |
| `tests/test_bigrace.py` | Create | DB helper tests for enrollment/config, payout math tests |
| `main.py` | Modify | Load `cogs.bigrace` |
| `.gitignore` | Modify | Replace `betting.db` with `data/betting.db` |

---

## Task 1: Update `database.py` — path, schema, and helpers

**Files:**
- Modify: `database.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_database.py`

- [ ] **Step 1: Write failing tests for new schema and helpers**

Add to `tests/test_database.py`:

```python
class TestSetupDbNewSchema:
    def test_users_table_has_monies_column(self, in_memory_db):
        cols = [row[1] for row in in_memory_db.execute("PRAGMA table_info(users)").fetchall()]
        assert "monies" in cols

    def test_users_table_has_carats_column(self, in_memory_db):
        cols = [row[1] for row in in_memory_db.execute("PRAGMA table_info(users)").fetchall()]
        assert "carats" in cols

    def test_users_table_has_no_points_column(self, in_memory_db):
        cols = [row[1] for row in in_memory_db.execute("PRAGMA table_info(users)").fetchall()]
        assert "points" not in cols

    def test_creates_race_config_table(self, in_memory_db):
        assert table_exists(in_memory_db, "race_config")

    def test_creates_race_notifications_table(self, in_memory_db):
        assert table_exists(in_memory_db, "race_notifications")


class TestGetUserMonies:
    def test_new_user_gets_1000_monies(self, in_memory_db):
        assert database.get_user_monies("user1", "guild1") == 1000

    def test_new_user_row_is_created(self, in_memory_db):
        database.get_user_monies("user1", "guild1")
        row = in_memory_db.execute(
            "SELECT monies FROM users WHERE user_id='user1' AND guild_id='guild1'"
        ).fetchone()
        assert row is not None and row[0] == 1000

    def test_existing_user_returns_correct_monies(self, in_memory_db):
        in_memory_db.execute(
            "INSERT INTO users (user_id, guild_id, monies, carats, last_daily) VALUES (?,?,?,?,?)",
            ("user2", "guild1", 500, 0, None),
        )
        in_memory_db.commit()
        assert database.get_user_monies("user2", "guild1") == 500

    def test_users_isolated_by_guild(self, in_memory_db):
        database.get_user_monies("user1", "guild1")
        assert database.get_user_monies("user1", "guild2") == 1000


class TestUpdateMonies:
    def test_updates_existing_user(self, in_memory_db):
        database.get_user_monies("user1", "guild1")
        database.update_monies("user1", "guild1", 250)
        assert database.get_user_monies("user1", "guild1") == 250

    def test_update_does_not_affect_other_guild(self, in_memory_db):
        database.get_user_monies("user1", "guild1")
        database.get_user_monies("user1", "guild2")
        database.update_monies("user1", "guild1", 9999)
        assert database.get_user_monies("user1", "guild2") == 1000


class TestGetUserCarats:
    def test_new_user_gets_0_carats(self, in_memory_db):
        database.get_user_monies("user1", "guild1")  # ensure row exists
        assert database.get_user_carats("user1", "guild1") == 0

    def test_returns_correct_carats(self, in_memory_db):
        in_memory_db.execute(
            "INSERT INTO users (user_id, guild_id, monies, carats, last_daily) VALUES (?,?,?,?,?)",
            ("user1", "guild1", 1000, 50, None),
        )
        in_memory_db.commit()
        assert database.get_user_carats("user1", "guild1") == 50


class TestUpdateCarats:
    def test_updates_carats(self, in_memory_db):
        in_memory_db.execute(
            "INSERT INTO users (user_id, guild_id, monies, carats, last_daily) VALUES (?,?,?,?,?)",
            ("user1", "guild1", 1000, 0, None),
        )
        in_memory_db.commit()
        database.update_carats("user1", "guild1", 25)
        assert database.get_user_carats("user1", "guild1") == 25


class TestAddDailyReward:
    def test_new_user_gets_starting_balance_plus_reward(self, in_memory_db):
        monies, carats = database.add_daily_reward("user1", "guild1")
        assert monies == 1100  # 1000 default + 100 reward
        assert carats == 10

    def test_existing_user_gets_reward_added(self, in_memory_db):
        in_memory_db.execute(
            "INSERT INTO users (user_id, guild_id, monies, carats, last_daily) VALUES (?,?,?,?,?)",
            ("user1", "guild1", 500, 5, None),
        )
        in_memory_db.commit()
        monies, carats = database.add_daily_reward("user1", "guild1")
        assert monies == 600
        assert carats == 15

    def test_sets_last_daily(self, in_memory_db):
        database.add_daily_reward("user1", "guild1")
        row = in_memory_db.execute(
            "SELECT last_daily FROM users WHERE user_id='user1' AND guild_id='guild1'"
        ).fetchone()
        assert row[0] is not None


class TestRaceConfig:
    def test_get_race_channel_returns_none_when_unset(self, in_memory_db):
        assert database.get_race_channel("guild1") is None

    def test_set_and_get_race_channel(self, in_memory_db):
        database.set_race_channel("guild1", "123456")
        assert database.get_race_channel("guild1") == "123456"

    def test_set_race_channel_overwrites(self, in_memory_db):
        database.set_race_channel("guild1", "111")
        database.set_race_channel("guild1", "222")
        assert database.get_race_channel("guild1") == "222"

    def test_get_all_race_configs_empty(self, in_memory_db):
        assert database.get_all_race_configs() == []

    def test_get_all_race_configs_returns_rows(self, in_memory_db):
        database.set_race_channel("guild1", "111")
        database.set_race_channel("guild2", "222")
        configs = database.get_all_race_configs()
        assert len(configs) == 2


class TestEnrollment:
    def test_not_enrolled_by_default(self, in_memory_db):
        assert database.is_enrolled("user1", "guild1") is False

    def test_toggle_enrolls_user(self, in_memory_db):
        result = database.toggle_enrollment("user1", "guild1")
        assert result is True
        assert database.is_enrolled("user1", "guild1") is True

    def test_toggle_unenrolls_user(self, in_memory_db):
        database.toggle_enrollment("user1", "guild1")
        result = database.toggle_enrollment("user1", "guild1")
        assert result is False
        assert database.is_enrolled("user1", "guild1") is False

    def test_enrollment_isolated_by_guild(self, in_memory_db):
        database.toggle_enrollment("user1", "guild1")
        assert database.is_enrolled("user1", "guild2") is False

    def test_get_enrolled_users(self, in_memory_db):
        database.toggle_enrollment("user1", "guild1")
        database.toggle_enrollment("user2", "guild1")
        database.toggle_enrollment("user1", "guild2")  # different guild
        users = database.get_enrolled_users("guild1")
        assert set(users) == {"user1", "user2"}
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
source venv/bin/activate && python3 -m pytest tests/test_database.py -v -k "NewSchema or GetUserMonies or UpdateMonies or GetUserCarats or UpdateCarats or AddDailyReward or RaceConfig or Enrollment" 2>&1 | tail -20
```

Expected: multiple failures — `get_user_monies`, `update_monies`, etc. not found.

- [ ] **Step 3: Remove old tests that reference `points` column directly**

In `tests/test_database.py`, remove or update `TestGetUserPoints` and `TestUpdatePoints` — replace with `TestGetUserMonies` and `TestUpdateMonies` above. Also remove the raw `points` column INSERT in `TestGetUserPoints.test_existing_user_returns_correct_points`.

- [ ] **Step 4: Rewrite `database.py`**

Replace the entire file:

```python
import sqlite3
import os
from datetime import datetime

_db_dir = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(_db_dir, exist_ok=True)
_db_path = os.path.join(_db_dir, "betting.db")
conn = sqlite3.connect(_db_path)
c = conn.cursor()


def setup_db():
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id    TEXT NOT NULL,
        guild_id   TEXT NOT NULL,
        monies     INTEGER NOT NULL DEFAULT 1000,
        carats     INTEGER NOT NULL DEFAULT 0,
        last_daily TEXT,
        PRIMARY KEY (user_id, guild_id)
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS bets (
        bet_id      INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id    TEXT,
        creator_id  TEXT,
        description TEXT,
        status      TEXT DEFAULT 'open'
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS bet_options (
        option_id    INTEGER PRIMARY KEY AUTOINCREMENT,
        bet_id       INTEGER,
        name         TEXT,
        total_amount INTEGER DEFAULT 0
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS wagers (
        wager_id  INTEGER PRIMARY KEY AUTOINCREMENT,
        bet_id    INTEGER,
        option_id INTEGER,
        user_id   TEXT,
        amount    INTEGER
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS race_config (
        guild_id   TEXT PRIMARY KEY,
        channel_id TEXT NOT NULL
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS race_notifications (
        user_id  TEXT NOT NULL,
        guild_id TEXT NOT NULL,
        PRIMARY KEY (user_id, guild_id)
    )
    """)
    conn.commit()


def get_user_monies(user_id, guild_id):
    c.execute(
        "SELECT monies FROM users WHERE user_id=? AND guild_id=?",
        (str(user_id), str(guild_id)),
    )
    result = c.fetchone()
    if result is None:
        c.execute(
            "INSERT INTO users (user_id, guild_id, monies, carats, last_daily) VALUES (?,?,?,?,?)",
            (str(user_id), str(guild_id), 1000, 0, None),
        )
        conn.commit()
        return 1000
    return result[0]


def update_monies(user_id, guild_id, monies):
    c.execute(
        "UPDATE users SET monies=? WHERE user_id=? AND guild_id=?",
        (monies, str(user_id), str(guild_id)),
    )
    conn.commit()


def get_user_carats(user_id, guild_id):
    c.execute(
        "SELECT carats FROM users WHERE user_id=? AND guild_id=?",
        (str(user_id), str(guild_id)),
    )
    result = c.fetchone()
    return result[0] if result else 0


def update_carats(user_id, guild_id, carats):
    c.execute(
        "UPDATE users SET carats=? WHERE user_id=? AND guild_id=?",
        (carats, str(user_id), str(guild_id)),
    )
    conn.commit()


def add_daily_reward(user_id, guild_id, monies=100, carats=10):
    """Write the daily reward. Returns (new_monies, new_carats).
    Cooldown checking is the caller's responsibility.
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute(
        "SELECT monies, carats FROM users WHERE user_id=? AND guild_id=?",
        (str(user_id), str(guild_id)),
    )
    row = c.fetchone()
    if row is None:
        new_monies = 1000 + monies
        new_carats = carats
        c.execute(
            "INSERT INTO users (user_id, guild_id, monies, carats, last_daily) VALUES (?,?,?,?,?)",
            (str(user_id), str(guild_id), new_monies, new_carats, now),
        )
    else:
        new_monies = row[0] + monies
        new_carats = row[1] + carats
        c.execute(
            "UPDATE users SET monies=?, carats=?, last_daily=? WHERE user_id=? AND guild_id=?",
            (new_monies, new_carats, now, str(user_id), str(guild_id)),
        )
    conn.commit()
    return new_monies, new_carats


def get_race_channel(guild_id):
    c.execute(
        "SELECT channel_id FROM race_config WHERE guild_id=?", (str(guild_id),)
    )
    row = c.fetchone()
    return row[0] if row else None


def set_race_channel(guild_id, channel_id):
    c.execute(
        "INSERT INTO race_config (guild_id, channel_id) VALUES (?,?) "
        "ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id",
        (str(guild_id), str(channel_id)),
    )
    conn.commit()


def get_all_race_configs():
    c.execute("SELECT guild_id, channel_id FROM race_config")
    return c.fetchall()


def is_enrolled(user_id, guild_id):
    c.execute(
        "SELECT 1 FROM race_notifications WHERE user_id=? AND guild_id=?",
        (str(user_id), str(guild_id)),
    )
    return c.fetchone() is not None


def toggle_enrollment(user_id, guild_id):
    if is_enrolled(user_id, guild_id):
        c.execute(
            "DELETE FROM race_notifications WHERE user_id=? AND guild_id=?",
            (str(user_id), str(guild_id)),
        )
        conn.commit()
        return False
    else:
        c.execute(
            "INSERT INTO race_notifications (user_id, guild_id) VALUES (?,?)",
            (str(user_id), str(guild_id)),
        )
        conn.commit()
        return True


def get_enrolled_users(guild_id):
    c.execute(
        "SELECT user_id FROM race_notifications WHERE guild_id=?", (str(guild_id),)
    )
    return [row[0] for row in c.fetchall()]
```

- [ ] **Step 5: Update `tests/conftest.py` — fix INSERT in fixture**

The `in_memory_db` fixture calls `database.setup_db()` which now creates the new schema. No changes needed to `conftest.py` itself — the autouse fixture handles it. However, any raw INSERTs in test files that reference the old `points` column must be updated to `monies`. Scan `tests/test_database.py` for `"points"` and update to `"monies"`.

- [ ] **Step 6: Run all database tests**

```bash
source venv/bin/activate && python3 -m pytest tests/test_database.py -v 2>&1 | tail -30
```

Expected: all pass.

- [ ] **Step 7: Delete old DB and update `.gitignore`**

```bash
rm -f betting.db
```

In `.gitignore`, replace `betting.db` with `data/betting.db`.

- [ ] **Step 8: Commit**

```bash
git add database.py tests/test_database.py .gitignore
git commit -S -m "feat: rename points→monies, add carats, new DB helpers and tables"
```

---

## Task 2: Update existing cogs to use new helpers and display "monies"

**Files:**
- Modify: `cogs/economy.py`
- Modify: `cogs/betting.py`
- Modify: `cogs/horserace.py`

- [ ] **Step 1: Update `cogs/economy.py`**

Change the import line:
```python
# Before:
from database import c, conn, get_user_points, update_points
# After:
from database import c, conn, get_user_monies, update_monies, add_daily_reward
```

Update `!balance` command body:
```python
monies = get_user_monies(ctx.author.id, ctx.guild.id)
embed = info_embed(
    "💰 Balance",
    f"{ctx.author.mention}, you have **{monies}** monies.",
    discord.Color.gold()
)
embed.set_footer(text="Use !daily to claim a daily reward.")
```

Update `!leaderboard` — change the SQL column and display string:
```python
c.execute(
    "SELECT user_id, monies FROM users WHERE guild_id=? "
    "ORDER BY monies DESC LIMIT 10",
    (str(ctx.guild.id),),
)
# ...
description += f"**{rank}** {name}: **{monies}** monies\n"
# ...
embed.set_footer(text="Use !balance to see your own monies.")
```

Rewrite `!daily` to use `add_daily_reward`:
```python
@commands.command(name="daily", help="Claim your daily 100 monies and 10 carats")
async def daily(self, ctx):
    user_id = str(ctx.author.id)
    guild_id = str(ctx.guild.id)

    now = datetime.now()
    c.execute(
        "SELECT monies, last_daily FROM users WHERE user_id=? AND guild_id=?",
        (user_id, guild_id),
    )
    result = c.fetchone()

    if result is not None:
        _, last_daily_str = result
        if last_daily_str:
            last_daily = datetime.strptime(last_daily_str, "%Y-%m-%d %H:%M:%S")
            time_passed = now - last_daily
            if time_passed < timedelta(hours=24):
                time_left = timedelta(hours=24) - time_passed
                hours, remainder = divmod(int(time_left.total_seconds()), 3600)
                minutes, _ = divmod(remainder, 60)
                embed = info_embed(
                    "⏰ Daily Cooldown",
                    f"{ctx.author.mention}, you must wait **{hours}h {minutes}m** before claiming again.",
                    discord.Color.orange()
                )
                await ctx.send(embed=embed)
                return

    new_monies, new_carats = add_daily_reward(user_id, guild_id)
    embed = info_embed(
        "🎁 Daily Reward",
        f"{ctx.author.mention}, you collected your daily reward!\n"
        f"**+100** monies · **+10** carats\n"
        f"Balance: **{new_monies}** monies · **{new_carats}** carats",
        discord.Color.green()
    )
    await ctx.send(embed=embed)
```

- [ ] **Step 2: Update `cogs/betting.py`**

Change import:
```python
from database import c, conn, get_user_monies, update_monies
```

Replace all `get_user_points` → `get_user_monies` and `update_points` → `update_monies`.

Replace all display strings "points" → "monies":
- `f"Insufficient points! You have {user_points} points."` → `f"Insufficient monies! You have {user_monies} monies."`
- `f"({total_amount} points, Payout: {odds_str})"` → `f"({total_amount} monies, Payout: {odds_str})"`
- `f"How many points do you want to bet"` → `f"How many monies do you want to bet"`
- `f"Potential payout: **{est_payout}** points"` → `f"Potential payout: **{est_payout}** monies"`

- [ ] **Step 3: Update `cogs/horserace.py`**

Change import:
```python
from database import get_user_monies, update_monies
```

Replace all `get_user_points` → `get_user_monies` and `update_points` → `update_monies`.

Replace display strings in payout lines:
- `f"💰 {display}: **+{payout}** points (bet {amt})"` → `f"💰 {display}: **+{payout}** monies (bet {amt})"`
- In `!racebet` confirmation: `"Morning line odds: **{frac}**"` — no "points" here, already fine.
- In `error_embed`: `f"Insufficient points! You have **{user_points}** points."` → `f"Insufficient monies! You have **{user_monies}** monies."`

- [ ] **Step 4: Run full test suite**

```bash
source venv/bin/activate && python3 -m pytest tests/ -v 2>&1 | tail -30
```

Expected: all pass. (Horserace and helpers tests should still pass since they don't test Discord layer directly.)

- [ ] **Step 5: Commit**

```bash
git add cogs/economy.py cogs/betting.py cogs/horserace.py
git commit -S -m "feat: update all cogs to use monies helpers and display strings"
```

---

## Task 3: Create `cogs/bigrace.py`

**Files:**
- Create: `cogs/bigrace.py`
- Create: `tests/test_bigrace.py`

- [ ] **Step 1: Write failing tests for payout math and enrollment**

Create `tests/test_bigrace.py`:

```python
import pytest
import database


class TestBigRacePayouts:
    """Test the parimutuel payout math in isolation (no Discord)."""

    def _compute_payouts(self, all_bets, winner_num):
        """Mirrors _run_big_race payout logic."""
        total_pool = sum(amt for _, amt in all_bets.values())
        winning_bets = {uid: amt for uid, (num, amt) in all_bets.items() if num == winner_num}
        winning_total = sum(winning_bets.values())
        if total_pool == 0 or winning_total == 0:
            return {}
        return {
            uid: int((amt / winning_total) * total_pool)
            for uid, amt in winning_bets.items()
        }

    def test_single_winner_gets_whole_pool(self):
        bets = {"user1": (1, 100), "user2": (2, 200)}
        payouts = self._compute_payouts(bets, winner_num=1)
        assert payouts == {"user1": 300}

    def test_two_winners_split_proportionally(self):
        bets = {"user1": (1, 100), "user2": (1, 200), "user3": (2, 300)}
        payouts = self._compute_payouts(bets, winner_num=1)
        assert payouts["user1"] == 200   # 100/300 * 600
        assert payouts["user2"] == 400   # 200/300 * 600

    def test_no_bets_returns_empty(self):
        assert self._compute_payouts({}, winner_num=1) == {}

    def test_no_winner_bets_returns_empty(self):
        bets = {"user1": (2, 100)}
        assert self._compute_payouts(bets, winner_num=1) == {}


class TestEnrollmentViaDb:
    def test_racenotify_toggle_on(self, in_memory_db):
        result = database.toggle_enrollment("user1", "guild1")
        assert result is True

    def test_racenotify_toggle_off(self, in_memory_db):
        database.toggle_enrollment("user1", "guild1")
        result = database.toggle_enrollment("user1", "guild1")
        assert result is False

    def test_get_enrolled_users_empty(self, in_memory_db):
        assert database.get_enrolled_users("guild1") == []

    def test_get_enrolled_users_after_enroll(self, in_memory_db):
        database.toggle_enrollment("user1", "guild1")
        database.toggle_enrollment("user2", "guild1")
        assert set(database.get_enrolled_users("guild1")) == {"user1", "user2"}

    def test_get_enrolled_users_excludes_other_guild(self, in_memory_db):
        database.toggle_enrollment("user1", "guild1")
        database.toggle_enrollment("user2", "guild2")
        assert database.get_enrolled_users("guild1") == ["user1"]


class TestRaceConfigViaDb:
    def test_no_config_returns_none(self, in_memory_db):
        assert database.get_race_channel("guild1") is None

    def test_set_and_retrieve_channel(self, in_memory_db):
        database.set_race_channel("guild1", "99999")
        assert database.get_race_channel("guild1") == "99999"

    def test_get_all_returns_all_guilds(self, in_memory_db):
        database.set_race_channel("guild1", "111")
        database.set_race_channel("guild2", "222")
        assert len(database.get_all_race_configs()) == 2
```

- [ ] **Step 2: Run tests to confirm they pass (DB tests) or are importable**

```bash
source venv/bin/activate && python3 -m pytest tests/test_bigrace.py -v 2>&1 | tail -20
```

Expected: all pass (these only test DB helpers and pure math, no Discord).

- [ ] **Step 3: Create `cogs/bigrace.py`**

```python
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
    simulate_race, estimate_win_rates, to_fractional_odds,
    format_race_progress, build_progress_bar,
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

        await ctx.send(embed=info_embed(
            "✅ Bet Placed",
            f"{ctx.author.mention} bet **{amount}** carats on **#{horse_number} {horse['name']}**!",
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
                " ".join(mentions) + " **The Daily Big Race is starting in 60 seconds — place your bets!**"
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

        self.active_big_races[guild_id] = {
            "horses": horses,
            "channel_id": channel_id,
            "betting_open": True,
        }

        # Build and send betting embed
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
                f"**#{h['number']} {h['name']}** — {label}\n"
                f"> 🔥\u2003{h['weight']}\u2003\u2003🔋\u2003{h['stamina']}\u2003\u2003🎯\u2003{h['consistency']}\u2003\u2003Odds: **{frac}**"
            )

        embed = discord.Embed(
            title="Daily Big Race!",
            description="Place your bets now! Use `!racebetbig <number> <amount>`.\n**Betting closes in 60 seconds.**",
            color=discord.Color.purple(),
        )
        embed.add_field(
            name="🔥 Weight  🔋 Stamina  🎯 Consistency",
            value="\n".join(lines),
            inline=False,
        )
        embed.set_footer(text="Odds are estimates only — actual payout is parimutuel. Bets use carats.")

        carat_file = discord.File(_CARAT_IMAGE, filename="carat.png")
        embed.set_thumbnail(url="attachment://carat.png")
        await channel.send(file=carat_file, embed=embed)

        await asyncio.sleep(60)

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

        total_pool = sum(amt for _, amt in all_bets.values())
        winning_bets = {uid: amt for uid, (num, amt) in all_bets.items() if num == winner_num}
        winning_total = sum(winning_bets.values())

        medals = ["🥇", "🥈", "🥉"]
        podium_lines = []
        for i, num in enumerate(finish_order[:3]):
            h = next(x for x in horses if x["number"] == num)
            medal = medals[i] if i < len(medals) else f"#{i + 1}"
            podium_lines.append(f"{medal} **#{num} {h['name']}**")

        payout_lines = []
        if total_pool == 0:
            payout_lines.append("No bets were placed — just a fun race!")
        elif winning_total == 0:
            for uid, (_, amt) in all_bets.items():
                carats = get_user_carats(uid, guild_id)
                update_carats(uid, guild_id, carats + amt)
            payout_lines.append(
                f"No one bet on **#{winner_num} {winner['name']}** — all carats refunded!"
            )
        else:
            guild_obj = self.bot.get_guild(guild_id)
            for uid, amt in winning_bets.items():
                payout = int((amt / winning_total) * total_pool)
                carats = get_user_carats(uid, guild_id)
                update_carats(uid, guild_id, carats + payout)
                if guild_obj:
                    member = guild_obj.get_member(int(uid))
                    display = member.display_name if member else f"<@{uid}>"
                else:
                    display = f"<@{uid}>"
                payout_lines.append(f"💰 {display}: **+{payout}** carats (bet {amt})")

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

        del self.active_big_races[guild_id]


async def setup(bot):
    await bot.add_cog(BigRace(bot))
```

**Note on thumbnail attachment:** `discord.File` is consumed on send and cannot be reused. The betting embed and results embed each need their own `discord.File` instance — the code above does this correctly with `carat_file` and `carat_file2`.

- [ ] **Step 4: Run bigrace tests**

```bash
source venv/bin/activate && python3 -m pytest tests/test_bigrace.py -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add cogs/bigrace.py tests/test_bigrace.py
git commit -S -m "feat: add bigrace cog with scheduler, !racenotify, !racebetbig, !setracechannel"
```

---

## Task 4: Wire up `main.py` and run full test suite

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Read `main.py`**

Open `main.py` and find where existing cogs are loaded.

- [ ] **Step 2: Add `cogs.bigrace` to the extension list**

Find the block that loads cogs (e.g. `await bot.load_extension("cogs.economy")`) and add:
```python
await bot.load_extension("cogs.bigrace")
```

- [ ] **Step 3: Add `backports.zoneinfo` to `requirements.txt` (Python <3.9 fallback)**

Add this line to `requirements.txt`:
```
backports.zoneinfo; python_version < "3.9"
```

- [ ] **Step 4: Run full test suite**

```bash
source venv/bin/activate && python3 -m pytest tests/ -v 2>&1 | tail -40
```

Expected: all tests pass. Note: cog-level Discord command tests (which require a live bot) are not in the suite — only DB helpers and simulation logic are tested.

- [ ] **Step 5: Final commit**

```bash
git add main.py requirements.txt
git commit -S -m "feat: load bigrace cog, add backports.zoneinfo to requirements"
```

---

## Manual Smoke Test Checklist

After all tasks are complete, run the bot locally (`python main.py`) and verify:

- [ ] `!balance` shows "monies" not "points"
- [ ] `!daily` shows monies + carats reward
- [ ] `!leaderboard` shows "monies"
- [ ] `!setracechannel #channel` stores the channel (requires Manage Server permission)
- [ ] `!setracechannel` (no args) shows the stored channel
- [ ] `!racenotify` toggles enrollment on/off
- [ ] `!race` still works (regular race unchanged)
- [ ] `!racebetbig` during a regular `!race` returns "No big race running"
- [ ] Bot starts without errors
