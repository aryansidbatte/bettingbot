# Daily Big Race — Design Spec

**Date:** 2026-03-23
**Status:** Draft

---

## Overview

A scheduled daily horse race that fires at 9pm Pacific Time in each configured guild. Uses a separate premium currency called **carats** (displayed using `carat.png`). Regular economy uses **monies**. Players can opt into push notifications via a toggle command.

---

## Currency

### Rename: points → monies
- The `points` column in `users` is renamed to `monies` in the new schema (DB is being deleted and recreated).
- All DB helpers are updated: `get_user_points` → `get_user_monies`, `update_points` → `update_monies`.
- All call sites across all cogs are updated accordingly.
- Every user-facing embed that says "points" is updated to "monies": `!balance`, `!daily`, `!leaderboard`, `!racebet`, `!bet`, and all payout messages.

### New currency: carats
- Stored as `carats INTEGER NOT NULL DEFAULT 0` on the `users` table.
- `get_user_carats(user_id, guild_id) -> int` and `update_carats(user_id, guild_id, new_total)` helpers (commit immediately, matching `update_points` behaviour).
- Carats are only spendable on the big race; monies are only spendable on regular races and bets.
- `!daily` awards both monies (100) and carats (10) per successful claim.

---

## Database Changes

The existing `betting.db` at the repo root is deleted. The new path is `data/betting.db`.

**First change applied:** `database.py` line 3 is updated from `sqlite3.connect("betting.db")` to `sqlite3.connect("data/betting.db")` so the bot connects to the correct file on import.

`.gitignore` is updated: remove the old `betting.db` root entry, add `data/betting.db`.

`data/betting.db` is created automatically by `setup_db()` on first bot start.

### Modified table: `users`
```sql
CREATE TABLE IF NOT EXISTS users (
    user_id   TEXT NOT NULL,
    guild_id  TEXT NOT NULL,
    monies    INTEGER NOT NULL DEFAULT 1000,
    carats    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, guild_id)
);
```

### New table: `race_config`
```sql
CREATE TABLE IF NOT EXISTS race_config (
    guild_id   TEXT PRIMARY KEY,
    channel_id TEXT NOT NULL
);
```

### New table: `race_notifications`
```sql
CREATE TABLE IF NOT EXISTS race_notifications (
    user_id  TEXT NOT NULL,
    guild_id TEXT NOT NULL,
    PRIMARY KEY (user_id, guild_id)
);
```

---

## `database.py` Changes

### `add_daily_reward(user_id, guild_id, monies=100, carats=10) -> tuple[int, int]`
Handles the write path only. On call:
- If the user row does not exist: INSERT with `monies=1000+monies, carats=carats, last_daily=now`.
- If the row exists: UPDATE `monies += monies, carats += carats, last_daily=now`.
- Returns `(new_monies, new_carats)`.

`economy.py !daily` retains its own `c.execute` SELECT to read `monies` and `last_daily` for the cooldown check and for displaying "X hours remaining" on the cooldown path. Only when the cooldown has passed does it call `add_daily_reward` and use the returned tuple for the confirmation embed. The raw INSERT/UPDATE in `economy.py` is removed; the SELECT is kept.

`!leaderboard` continues to use `c, conn` directly for its raw SELECT (column is now `monies`) — that query is not otherwise refactored. The `from database import c, conn` import in `economy.py` remains.

### New helpers
- `get_user_monies(user_id, guild_id) -> int` (replaces `get_user_points`)
- `update_monies(user_id, guild_id, new_total)` (replaces `update_points`)
- `get_user_carats(user_id, guild_id) -> int`
- `update_carats(user_id, guild_id, new_total)` — commits immediately
- `get_race_channel(guild_id) -> str | None` — returns `None` if not configured
- `set_race_channel(guild_id, channel_id)`
- `is_enrolled(user_id, guild_id) -> bool`
- `toggle_enrollment(user_id, guild_id) -> bool` — returns new enrolled state (True = enrolled)

---

## Python Version

Requires **Python 3.9+** for `zoneinfo` (stdlib). Add `backports.zoneinfo; python_version < "3.9"` to `requirements.txt` as a fallback.

---

## New Cog: `cogs/bigrace.py`

Separate from `horserace.py`. Reuses `simulate_race`, `estimate_win_rates`, `to_fractional_odds`, `format_race_progress`, `build_progress_bar`, `HORSE_NAMES`, `HORSE_IMAGES` from `horserace.py`.

### In-memory race state

```python
self.active_big_races: dict[int, dict] = {}  # guild_id -> race_state
```

Race state keys: `horses`, `channel_id`, `betting_open`. Created when the scheduler fires; deleted after race completes or is abandoned.

**Known limitation:** If the bot restarts during an active betting window, any carats already deducted from users in that race are permanently lost. This is accepted behaviour for the current scope — the bot is not yet deployed and a recovery mechanism is out of scope.

**Concurrent race guard:** Before starting a big race for a guild, `_run_big_race` checks if a regular `!race` is active in the same guild by inspecting the `HorseRace` cog's `active_races` dict via `self.bot.cogs["HorseRace"].active_races`. If a regular race is active, the big race is skipped for that guild with no message (it will run again the next day). This prevents interleaved embeds in the same channel.

The `!racebetbig` confirmation embed is sent to the channel where the user ran the command (same as `!racebet`), not restricted to the race channel.

### Loop lifecycle

`daily_race.start()` is called in `cog_load` (or `__init__` via `self.daily_race.start()`).
`daily_race.cancel()` is called in `cog_unload` to prevent duplicate loops on cog reload.

```python
@daily_race.before_loop
async def before_daily_race(self):
    await self.bot.wait_until_ready()
```

This ensures the loop does not fire before the bot finishes connecting.

### Scheduler

```python
from zoneinfo import ZoneInfo
import datetime
from discord.ext import tasks

@tasks.loop(time=datetime.time(21, 0, tzinfo=ZoneInfo("America/Los_Angeles")))
async def daily_race(self):
    rows = get_all_race_configs()  # SELECT guild_id, channel_id FROM race_config
    for guild_id, channel_id in rows:
        asyncio.create_task(self._run_big_race(int(guild_id), int(channel_id)))
```

Each configured guild gets its own `asyncio.create_task`. No per-bot cap on concurrent guild races — at the expected scale this is acceptable.

`get_all_race_configs() -> list[tuple[str, str]]` is added to `database.py`.

### Commands

#### `!setracechannel [#channel]`
- Requires `manage_guild` permission.
- With a channel arg: calls `set_race_channel`, confirms with a green embed: "✅ Big race channel set to #channel-name."
- With no args: calls `get_race_channel`. If configured, replies "📍 Big race channel: #channel-name (or ID if channel not found in guild)." If `None`, replies "No big race channel configured. Use `!setracechannel #channel`."

#### `!racenotify`
- Toggle notification enrollment.
- Calls `toggle_enrollment(user_id, guild_id)`.
- If newly enrolled: green embed — "✅ **You're in!** You'll be pinged before the daily big race at 9pm PT."
- If unenrolled: grey embed — "🔕 **Removed.** You won't be pinged for the daily big race."

#### `!racebetbig <number> <amount>`
- Valid from any channel in the guild (same as `!racebet`).
- Requires an active big race in the guild with `betting_open=True`.
- Validates: `amount > 0`, user has sufficient carats, horse number is valid, user hasn't already bet in this race.
- One bet per user per race. No maximum bet cap.
- Deducts carats immediately via `update_carats`.
- Confirmation embed: "✅ Bet placed — **{amount}** carats on **#{n} {horse name}**."

### `_run_big_race(guild_id, channel_id)`

1. Fetch channel object via `self.bot.get_channel(channel_id)`. If `None` or bot lacks send permission, return silently.
2. Fetch enrolled user IDs for the guild. For each, attempt `guild.get_member(user_id)`. Skip silently if member not found (left server). Build mention string from found members.
3. If any enrolled members: send a plain message `"{mentions} **The Daily Big Race is starting in 60 seconds — place your bets!**"` (no emoji — carat.png image appears in the betting embed that follows immediately after).
4. Build horses, compute odds, send betting embed (purple, carat.png thumbnail, same field layout as `!race`).
5. Wait 60 seconds.
6. Set `betting_open = False`.
7. Simulate race, animate progress (same 9-checkpoint flow as `horserace.py`).
8. Compute parimutuel payouts in carats:
   - No bets placed → "No bets placed — just a fun race!" (no payout).
   - No bets on winner → refund all bets in carats to each bettor.
   - Otherwise → standard parimutuel split.
   - Payout display names: call `self.bot.get_guild(guild_id)` to get the guild object, then `guild.get_member(uid)` for each winner. If `guild` is `None` or `get_member` returns `None`, fall back to `<@{uid}>`.
9. Send results embed. Each `discord.File("data/carat.png", filename="carat.png")` is instantiated fresh per race call (not reused across guilds).
10. `del self.active_big_races[guild_id]`.

### Embed branding

- `carat.png` is an existing asset at `data/carat.png`. Each `_run_big_race` call opens its own `discord.File("data/carat.png", filename="carat.png")` instance.
- Thumbnail: `embed.set_thumbnail(url="attachment://carat.png")`.
- Title: "Daily Big Race!"
- Color: `discord.Color.purple()`
- No 🥕 emoji used anywhere — carat.png image serves as the visual currency indicator.

---

## `main.py`

Load `cogs.bigrace` alongside existing cogs.

---

## Out of Scope

- Carat leaderboard
- Cross-server carat economy
- Big race history / stats
- Admin command to manually trigger the big race
- Mid-race crash recovery / carat refund on restart
