# Claude Code Configuration

## Workflow Rules

1. Never jump straight to code — brainstorm and plan first
2. Show plans in chunks for approval before executing
3. Write failing tests before writing implementation code
4. Verify work before declaring any task complete
5. One feature per branch, PR before merge

## Behavioral Rules (Always Enforced)

- NEVER add Co-Authored-By lines to commit messages
- Do what has been asked; nothing more, nothing less
- NEVER create files unless they're absolutely necessary for achieving your goal
- ALWAYS prefer editing an existing file to creating a new one
- NEVER proactively create documentation files (*.md) or README files unless explicitly requested
- NEVER save working files, text/mds, or tests to the root folder
- ALWAYS read a file before editing it
- NEVER commit secrets, credentials, or .env files

## File Organization

- NEVER save to root folder — use the directories below
- Use `/tests` for test files
- Use `/docs` for documentation and markdown files
- Use `/cogs` for bot cogs
- Use `/data` for data files (e.g. horses.json)

## Project Architecture

- Keep files under 500 lines
- Prefer TDD London School (mock-first) for new code
- Ensure input validation at system boundaries

## Build & Test

```bash
# Test
source venv/bin/activate && python3 -m pytest tests/ -v

# Run bot
python main.py
```

- ALWAYS run tests after making code changes

## Security Rules

- NEVER hardcode API keys, secrets, or credentials in source files
- NEVER commit .env files or any file containing secrets

## Bettingbot Project

### What This Project Is

A Python-based Discord betting bot where server members earn virtual points and spend them on two types of betting:
1. **Custom bets** — any server member creates an arbitrary multi-outcome parimutuel bet (e.g. "Who wins the game?"), others wager points on outcomes, and the creator resolves the winner.
2. **Horse races** — simulated races with 4–6 randomly selected horses, a 60-second betting window, animated mid-race progress (via message edits), and parimutuel payouts.

Points are isolated per Discord server (guild). New users start with 1,000 points.

### Entry Point

`main.py` — creates the `discord.Bot` instance, calls `database.setup_db()`, loads all cogs, then starts the bot via `asyncio.run(main())`.

### Discord Library

**discord.py 2.6.4** — uses `discord.ext.commands` with a `!` prefix. All commands are prefix-based (`commands.Cog`); no slash commands yet.

### What the Bot Currently Does

| Command | Cog | Description |
|---------|-----|-------------|
| `!balance` | economy | Show your points |
| `!daily` | economy | Claim 100 points (24h cooldown) |
| `!leaderboard` / `!lb` / `!top` | economy | Top 10 users by points in the server |
| `!createbet` | betting | Interactively create a multi-outcome bet |
| `!bets` | betting | List all open bets with pools and payout odds |
| `!bet` | betting | Interactively place a wager on an open bet |
| `!resolve <bet_id>` | betting | Resolve a bet you created; distribute winnings |
| `!race` | horserace | Start a horse race with 60-second betting window |
| `!racebet <number> <amount>` | horserace | Bet on a horse during the betting window |
| `!help` | misc | Custom help embed listing all commands |

### How to Run Locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "DISCORD_TOKEN=your_token_here" > .env
python main.py
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_TOKEN` | Yes | Discord bot token, loaded from `.env` via python-dotenv |

`.env` is gitignored. No other env vars are used.

### File Structure

```
bettingbot/
├── main.py           # Entry point: bot setup, cog loading, asyncio runner
├── database.py       # SQLite helpers: setup_db, get_user_monies, update_points, vc helpers
│                     #   Tables: users, bets, bet_options, wagers
├── helpers.py        # Shared utilities: info_embed, error_embed, get_reply_or_cancel
├── data/
│   └── horses.json   # 141 Uma Musume horse names + image URLs
├── cogs/
│   ├── economy.py    # !balance, !daily, !leaderboard
│   ├── betting.py    # !createbet, !bets, !bet, !resolve
│   ├── misc.py       # !help (custom help command)
│   ├── horserace.py  # !race, !racebet — simulation, Monte Carlo odds, parimutuel payouts
│   └── vcrewards.py  # Voice channel carat rewards (1 carat/hour)
└── requirements.txt
```

### Coding Conventions

- Every cog is a `commands.Cog` subclass with `async def setup(bot)` at the bottom
- All user-facing responses use Discord embeds via `info_embed` / `error_embed` from `helpers.py`
- Points are always read/written through `get_user_monies(user_id, guild_id)` / `update_points(user_id, guild_id, new_total)`
- Multi-step interactive input uses `get_reply_or_cancel(bot, ctx, prompt)` which handles timeouts and `cancel`
- Discord IDs are stored as `TEXT` in SQLite and always cast via `str()`
- Bot prefix is `!`; `help_command=None` disables the default help in favour of the custom `!help`

### Known Incomplete Areas & Technical Debt

| Issue | Location | Notes |
|-------|----------|-------|
| Module-level SQLite connection (`conn`, `c`) shared across cogs | `database.py:3` | Not thread-safe; fine for single-process but fragile under concurrent writes |
| `economy.py` imports `c, conn` directly for raw SQL | `cogs/economy.py:5` | Leaks DB internals into cog layer; `daily` command bypasses `update_points` |
| Race state is in-memory only | `cogs/horserace.py` | Lost on bot restart; by design for now but prevents history/stats |
| No slash commands — only `!` prefix | all cogs | Discord is pushing apps toward slash commands |
| No guild guard — `ctx.guild` assumed not None | all cogs | Bot would crash if a user ran commands in a DM |
| Only the bet creator can resolve a bet | `cogs/betting.py` | No admin/moderator override |
| No per-user stats, bet history, or win rate tracking | `database.py` | Users can only see current balance |

### Planned Features

- **User stats** — `!stats [@user]` showing total wagered, win rate, bets created/won, races entered
- **Bet history** — `!history` listing past bets a user participated in with outcomes and payouts
- **Slash commands** — migrate to `discord.app_commands` alongside or replacing prefix commands
- **Admin commands** — force-close bets, adjust points, mod overrides for resolution
