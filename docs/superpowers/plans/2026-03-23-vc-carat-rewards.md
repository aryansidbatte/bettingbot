# VC Carat Rewards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Award 1 carat per hour to users who spend time in non-AFK voice channels, tracked per-minute in the DB so progress survives bot restarts.

**Architecture:** A `vc_minutes` column is added to the `users` table. A new `VCRewards` cog maintains an in-memory set of currently eligible users (non-AFK, non-self-deafened, non-bot), updated via `on_voice_state_update`. A `tasks.loop(minutes=1)` tick increments `vc_minutes` in the DB for each eligible user; when a user's total reaches 60, one carat is awarded and the counter resets. Restart recovery is automatic since accumulated minutes survive in the DB and the cog re-syncs eligibility from current voice state on load.

**Tech Stack:** Python 3.9+, discord.py 2.6.4 (`discord.ext.commands`, `discord.ext.tasks`), SQLite via module-level `conn`/`c` in `database.py`, pytest with `in_memory_db` fixture.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `database.py` | Modify | Add `vc_minutes` column migration; add `get_vc_minutes`, `add_vc_minutes` helpers |
| `cogs/vcrewards.py` | Create | `VCRewards` cog: voice state listener, 1-minute tick loop, startup sync |
| `main.py` | Modify | Load `cogs.vcrewards` extension |
| `tests/test_database.py` | Modify | Tests for `vc_minutes` column and new helpers |
| `tests/test_vcrewards.py` | Create | Tests for cog eligibility logic |

---

## Task 1: DB — `vc_minutes` column + helpers

**Files:**
- Modify: `database.py`
- Modify: `tests/test_database.py`

### Step 1.1 — Write failing tests for schema

Add to `tests/test_database.py` inside `TestSetupDbNewSchema`:

```python
def test_users_table_has_vc_minutes_column(self, in_memory_db):
    cols = [row[1] for row in in_memory_db.execute("PRAGMA table_info(users)").fetchall()]
    assert "vc_minutes" in cols

def test_vc_minutes_defaults_to_zero(self, in_memory_db):
    database.get_user_monies("user1", "guild1")
    row = in_memory_db.execute(
        "SELECT vc_minutes FROM users WHERE user_id='user1' AND guild_id='guild1'"
    ).fetchone()
    assert row[0] == 0
```

Add a new `TestVCMinutes` class after `TestUpdateCarats`:

```python
class TestGetVcMinutes:
    def test_returns_zero_for_existing_user_with_no_minutes(self, in_memory_db):
        database.get_user_monies("user1", "guild1")
        assert database.get_vc_minutes("user1", "guild1") == 0

    def test_returns_zero_for_missing_user(self, in_memory_db):
        assert database.get_vc_minutes("nobody", "guild1") == 0

    def test_returns_stored_minutes(self, in_memory_db):
        in_memory_db.execute(
            "INSERT INTO users (user_id, guild_id, monies, carats, vc_minutes, last_daily)"
            " VALUES (?,?,?,?,?,?)",
            ("user1", "guild1", 1000, 0, 45, None),
        )
        in_memory_db.commit()
        assert database.get_vc_minutes("user1", "guild1") == 45


class TestAddVcMinutes:
    def test_increments_minutes(self, in_memory_db):
        database.get_user_monies("user1", "guild1")
        database.add_vc_minutes("user1", "guild1", delta=1)
        assert database.get_vc_minutes("user1", "guild1") == 1

    def test_no_carat_before_60(self, in_memory_db):
        database.get_user_monies("user1", "guild1")
        awarded = database.add_vc_minutes("user1", "guild1", delta=59)
        assert awarded == 0
        assert database.get_user_carats("user1", "guild1") == 0

    def test_awards_carat_at_60(self, in_memory_db):
        in_memory_db.execute(
            "INSERT INTO users (user_id, guild_id, monies, carats, vc_minutes, last_daily)"
            " VALUES (?,?,?,?,?,?)",
            ("user1", "guild1", 1000, 0, 59, None),
        )
        in_memory_db.commit()
        awarded = database.add_vc_minutes("user1", "guild1", delta=1)
        assert awarded == 1
        assert database.get_user_carats("user1", "guild1") == 1

    def test_resets_minutes_after_award(self, in_memory_db):
        in_memory_db.execute(
            "INSERT INTO users (user_id, guild_id, monies, carats, vc_minutes, last_daily)"
            " VALUES (?,?,?,?,?,?)",
            ("user1", "guild1", 1000, 0, 59, None),
        )
        in_memory_db.commit()
        database.add_vc_minutes("user1", "guild1", delta=1)
        assert database.get_vc_minutes("user1", "guild1") == 0

    def test_no_row_returns_zero_does_not_crash(self, in_memory_db):
        awarded = database.add_vc_minutes("nobody", "guild1", delta=1)
        assert awarded == 0

    def test_isolated_by_guild(self, in_memory_db):
        database.get_user_monies("user1", "guild1")
        database.get_user_monies("user1", "guild2")
        database.add_vc_minutes("user1", "guild1", delta=30)
        assert database.get_vc_minutes("user1", "guild2") == 0
```

- [ ] **Step 1.2 — Run tests to verify they fail**

```bash
source venv/bin/activate && python3 -m pytest tests/test_database.py -k "vc_minutes or VcMinutes or AddVc or GetVc" -v
```
Expected: FAIL (column and helpers don't exist yet)

- [ ] **Step 1.3 — Update `setup_db` in `database.py`: add `vc_minutes` to `CREATE TABLE` and add migration for existing DBs**

**1a.** Update the `CREATE TABLE IF NOT EXISTS users` statement to include `vc_minutes` as the last column (before the `PRIMARY KEY` line):

```python
    CREATE TABLE IF NOT EXISTS users (
        user_id    TEXT NOT NULL,
        guild_id   TEXT NOT NULL,
        monies     INTEGER NOT NULL DEFAULT 1000,
        carats     INTEGER NOT NULL DEFAULT 0,
        vc_minutes INTEGER NOT NULL DEFAULT 0,
        last_daily TEXT,
        PRIMARY KEY (user_id, guild_id)
    )
```

**1b.** After the last `c.execute("""CREATE TABLE IF NOT EXISTS race_notifications...""")` block and before `conn.commit()`, add the migration for existing installs:

```python
# Migrate existing DBs: add vc_minutes column if it doesn't exist yet
try:
    c.execute("ALTER TABLE users ADD COLUMN vc_minutes INTEGER NOT NULL DEFAULT 0")
except sqlite3.OperationalError:
    pass  # column already exists
```

- [ ] **Step 1.4 — Add `get_vc_minutes` helper to `database.py`**

Add after `update_carats`:

```python
def get_vc_minutes(user_id, guild_id):
    c.execute(
        "SELECT vc_minutes FROM users WHERE user_id=? AND guild_id=?",
        (str(user_id), str(guild_id)),
    )
    result = c.fetchone()
    return result[0] if result else 0
```

- [ ] **Step 1.5 — Add `add_vc_minutes` helper to `database.py`**

Add after `get_vc_minutes`:

```python
def add_vc_minutes(user_id, guild_id, delta=1):
    """Increment VC minutes by delta. Awards carats when accumulated >= 60.
    Returns number of carats awarded (0 or 1 in normal operation).
    Row must exist (call get_user_monies first to auto-create).
    """
    c.execute(
        "SELECT vc_minutes, carats FROM users WHERE user_id=? AND guild_id=?",
        (str(user_id), str(guild_id)),
    )
    row = c.fetchone()
    if row is None:
        return 0
    new_minutes = row[0] + delta
    carats_awarded = new_minutes // 60
    new_minutes = new_minutes % 60
    new_carats = row[1] + carats_awarded
    c.execute(
        "UPDATE users SET vc_minutes=?, carats=? WHERE user_id=? AND guild_id=?",
        (new_minutes, new_carats, str(user_id), str(guild_id)),
    )
    conn.commit()
    return carats_awarded
```

- [ ] **Step 1.6 — Run tests to verify they pass**

```bash
source venv/bin/activate && python3 -m pytest tests/test_database.py -v
```
Expected: all pass

- [ ] **Step 1.7 — Commit**

```bash
git add database.py tests/test_database.py
git commit -m "feat: add vc_minutes column and add_vc_minutes helper to database"
```

---

## Task 2: VCRewards cog

**Files:**
- Create: `cogs/vcrewards.py`
- Create: `tests/test_vcrewards.py`

- [ ] **Step 2.0 — Add `pytest-asyncio`, create `pytest.ini`, and commit**

**2.0a** — Open `requirements.txt` and add `pytest-asyncio` on a new line after the existing pytest entry. Then install it:

```bash
source venv/bin/activate && pip install pytest-asyncio
```

**2.0b** — Create `pytest.ini` in the project root with:

```ini
[pytest]
asyncio_mode = auto
```

This makes pytest-asyncio treat all `async def test_*` functions and methods as asyncio tests automatically, without needing `@pytest.mark.asyncio` on each one.

**2.0c** — Commit both files:

```bash
git add requirements.txt pytest.ini
git commit -m "chore: add pytest-asyncio with auto asyncio_mode"
```

- [ ] **Step 2.1 — Write failing tests**

Create `tests/test_vcrewards.py`:

```python
import sys
import os
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# asyncio_mode = auto is set in pytest.ini — no marks needed on individual tests.


def make_member(user_id, guild_id, self_deaf=False, bot=False):
    """Build a minimal mock discord.Member."""
    member = MagicMock()
    member.id = user_id
    member.bot = bot
    guild = MagicMock()
    guild.id = guild_id
    guild.afk_channel = None
    member.guild = guild
    voice = MagicMock()
    voice.self_deaf = self_deaf
    member.voice = voice
    return member


def make_voice_state(channel=None, self_deaf=False):
    vs = MagicMock()
    vs.channel = channel
    vs.self_deaf = self_deaf
    return vs


def make_channel(channel_id):
    ch = MagicMock()
    ch.id = channel_id
    return ch


@pytest.fixture
def cog():
    """Bare VCRewards instance with __init__ bypassed (no tasks started)."""
    from cogs.vcrewards import VCRewards
    bot = MagicMock()
    bot.guilds = []
    c = VCRewards.__new__(VCRewards)
    c.bot = bot
    c.active_vc = set()
    return c


class TestOnVoiceStateUpdate:
    async def test_user_joining_vc_added_to_active(self, cog):
        channel = make_channel(999)
        member = make_member(1, 100)
        before = make_voice_state(channel=None)
        after = make_voice_state(channel=channel, self_deaf=False)

        with patch("cogs.vcrewards.get_user_monies"):
            await cog.on_voice_state_update(member, before, after)

        assert (100, 1) in cog.active_vc

    async def test_user_leaving_vc_removed_from_active(self, cog):
        cog.active_vc.add((100, 1))
        channel = make_channel(999)
        member = make_member(1, 100)
        before = make_voice_state(channel=channel)
        after = make_voice_state(channel=None)

        with patch("cogs.vcrewards.get_user_monies"):
            await cog.on_voice_state_update(member, before, after)

        assert (100, 1) not in cog.active_vc

    async def test_self_deafened_user_removed(self, cog):
        cog.active_vc.add((100, 1))
        channel = make_channel(999)
        member = make_member(1, 100)
        before = make_voice_state(channel=channel, self_deaf=False)
        after = make_voice_state(channel=channel, self_deaf=True)

        with patch("cogs.vcrewards.get_user_monies"):
            await cog.on_voice_state_update(member, before, after)

        assert (100, 1) not in cog.active_vc

    async def test_self_muted_user_stays_active(self, cog):
        channel = make_channel(999)
        member = make_member(1, 100)
        before = make_voice_state(channel=None)
        after = make_voice_state(channel=channel, self_deaf=False)

        with patch("cogs.vcrewards.get_user_monies"):
            await cog.on_voice_state_update(member, before, after)

        assert (100, 1) in cog.active_vc

    async def test_bot_user_ignored(self, cog):
        channel = make_channel(999)
        member = make_member(1, 100, bot=True)
        before = make_voice_state(channel=None)
        after = make_voice_state(channel=channel)

        with patch("cogs.vcrewards.get_user_monies"):
            await cog.on_voice_state_update(member, before, after)

        assert (100, 1) not in cog.active_vc

    async def test_afk_channel_not_added(self, cog):
        afk = make_channel(777)
        member = make_member(1, 100)
        member.guild.afk_channel = afk
        before = make_voice_state(channel=None)
        after = make_voice_state(channel=afk, self_deaf=False)

        with patch("cogs.vcrewards.get_user_monies"):
            await cog.on_voice_state_update(member, before, after)

        assert (100, 1) not in cog.active_vc

    async def test_undeafen_adds_back_to_active(self, cog):
        channel = make_channel(999)
        member = make_member(1, 100)
        before = make_voice_state(channel=channel, self_deaf=True)
        after = make_voice_state(channel=channel, self_deaf=False)

        with patch("cogs.vcrewards.get_user_monies"):
            await cog.on_voice_state_update(member, before, after)

        assert (100, 1) in cog.active_vc
```

- [ ] **Step 2.2 — Run tests to verify they fail**

```bash
source venv/bin/activate && python3 -m pytest tests/test_vcrewards.py -v
```
Expected: FAIL (module doesn't exist)

- [ ] **Step 2.3 — Create `cogs/vcrewards.py`**

```python
import discord
from discord.ext import commands, tasks

from database import get_user_monies, add_vc_minutes


class VCRewards(commands.Cog):
    """Awards 1 carat per hour spent in eligible voice channels."""

    def __init__(self, bot):
        self.bot = bot
        self.active_vc: set[tuple] = set()  # (guild_id, user_id)
        self.vc_tick.start()

    def cog_unload(self):
        self.vc_tick.cancel()

    async def _sync_active_vc(self):
        """Populate active_vc from current voice state (called after bot is ready)."""
        for guild in self.bot.guilds:
            afk_id = guild.afk_channel.id if guild.afk_channel else None
            for vc in guild.voice_channels:
                if vc.id == afk_id:
                    continue
                for member in vc.members:
                    if member.bot or not member.voice or member.voice.self_deaf:
                        continue
                    self.active_vc.add((guild.id, member.id))
                    get_user_monies(member.id, guild.id)  # ensure row exists

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return
        guild = member.guild
        afk_id = guild.afk_channel.id if guild.afk_channel else None
        key = (guild.id, member.id)

        in_eligible = (
            after.channel is not None
            and after.channel.id != afk_id
            and not after.self_deaf
        )

        if in_eligible:
            self.active_vc.add(key)
            get_user_monies(member.id, guild.id)  # ensure row exists
        else:
            self.active_vc.discard(key)

    @tasks.loop(minutes=1)
    async def vc_tick(self):
        for guild_id, user_id in list(self.active_vc):
            add_vc_minutes(user_id, guild_id, delta=1)

    @vc_tick.before_loop
    async def before_vc_tick(self):
        await self.bot.wait_until_ready()
        await self._sync_active_vc()  # safe: bot is ready, guilds are populated


async def setup(bot):
    await bot.add_cog(VCRewards(bot))
```

- [ ] **Step 2.4 — Run tests to verify they pass**

```bash
source venv/bin/activate && python3 -m pytest tests/test_vcrewards.py -v
```
Expected: all pass

- [ ] **Step 2.5 — Commit**

```bash
git add cogs/vcrewards.py tests/test_vcrewards.py
git commit -m "feat: add VCRewards cog — 1 carat per hour in voice channels"
```

---

## Task 3: Wire up main.py + full test run

**Files:**
- Modify: `main.py`

- [ ] **Step 3.1 — Read `main.py` to find the extensions list**

Locate the `bot.load_extension` or equivalent calls.

- [ ] **Step 3.2 — Add `cogs.vcrewards` to the extension list in `main.py`**

Add `"cogs.vcrewards"` alongside the other four cog entries. No test needed — covered by the full suite.

- [ ] **Step 3.3 — Run full test suite**

```bash
source venv/bin/activate && python3 -m pytest tests/ -v
```
Expected: all tests pass (86 existing + new vcrewards + new db tests)

- [ ] **Step 3.4 — Commit**

```bash
git add main.py
git commit -m "feat: load VCRewards cog in main.py"
```

---

## Notes for implementer

- `add_vc_minutes` returns 0 if the user has no DB row. This is safe — `get_user_monies` is called on voice join and in `_sync_active_vc`, so rows always exist before the tick fires.
- `pytest-asyncio` is configured with `asyncio_mode = auto` in `pytest.ini` (created in Step 2.0). This means all `async def test_*` functions and methods run as asyncio tests without any marks needed.
- `_sync_active_vc` is called inside `before_vc_tick` (after `wait_until_ready`) — not in `cog_load` — so `self.bot.guilds` is guaranteed to be populated when sync runs.
- `tasks.loop(minutes=1)` fires once per minute per process. The single loop covers all guilds via the shared `active_vc` set.
- `member.voice` can technically be `None` for cached members in `_sync_active_vc`. The `not member.voice` guard handles this safely.
