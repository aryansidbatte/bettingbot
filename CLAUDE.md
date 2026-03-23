# Claude Code Configuration - RuFlo V3

## Workflow Rules

1. Never jump straight to code — brainstorm and plan first
2. Show plans in chunks for approval before executing
3. Write failing tests before writing implementation code
4. Verify work before declaring any task complete
5. One feature per branch, PR before merge

## Behavioral Rules (Always Enforced)

- Do what has been asked; nothing more, nothing less
- NEVER create files unless they're absolutely necessary for achieving your goal
- ALWAYS prefer editing an existing file to creating a new one
- NEVER proactively create documentation files (*.md) or README files unless explicitly requested
- NEVER save working files, text/mds, or tests to the root folder
- Never continuously check status after spawning a swarm — wait for results
- ALWAYS read a file before editing it
- NEVER commit secrets, credentials, or .env files

## File Organization

- NEVER save to root folder — use the directories below
- Use `/src` for source code files
- Use `/tests` for test files
- Use `/docs` for documentation and markdown files
- Use `/config` for configuration files
- Use `/scripts` for utility scripts
- Use `/examples` for example code

## Project Architecture

- Follow Domain-Driven Design with bounded contexts
- Keep files under 500 lines
- Use typed interfaces for all public APIs
- Prefer TDD London School (mock-first) for new code
- Use event sourcing for state changes
- Ensure input validation at system boundaries

### Project Config

- **Topology**: hierarchical-mesh
- **Max Agents**: 15
- **Memory**: hybrid
- **HNSW**: Enabled
- **Neural**: Enabled

## Build & Test

```bash
# Build
npm run build

# Test
npm test

# Lint
npm run lint
```

- ALWAYS run tests after making code changes
- ALWAYS verify build succeeds before committing

## Security Rules

- NEVER hardcode API keys, secrets, or credentials in source files
- NEVER commit .env files or any file containing secrets
- Always validate user input at system boundaries
- Always sanitize file paths to prevent directory traversal
- Run `npx @claude-flow/cli@latest security scan` after security-related changes

## Concurrency: 1 MESSAGE = ALL RELATED OPERATIONS

- All operations MUST be concurrent/parallel in a single message
- Use Claude Code's Task tool for spawning agents, not just MCP
- ALWAYS batch ALL todos in ONE TodoWrite call (5-10+ minimum)
- ALWAYS spawn ALL agents in ONE message with full instructions via Task tool
- ALWAYS batch ALL file reads/writes/edits in ONE message
- ALWAYS batch ALL Bash commands in ONE message

## Swarm Orchestration

- MUST initialize the swarm using CLI tools when starting complex tasks
- MUST spawn concurrent agents using Claude Code's Task tool
- Never use CLI tools alone for execution — Task tool agents do the actual work
- MUST call CLI tools AND Task tool in ONE message for complex work

### 3-Tier Model Routing (ADR-026)

| Tier | Handler | Latency | Cost | Use Cases |
|------|---------|---------|------|-----------|
| **1** | Agent Booster (WASM) | <1ms | $0 | Simple transforms (var→const, add types) — Skip LLM |
| **2** | Haiku | ~500ms | $0.0002 | Simple tasks, low complexity (<30%) |
| **3** | Sonnet/Opus | 2-5s | $0.003-0.015 | Complex reasoning, architecture, security (>30%) |

- Always check for `[AGENT_BOOSTER_AVAILABLE]` or `[TASK_MODEL_RECOMMENDATION]` before spawning agents
- Use Edit tool directly when `[AGENT_BOOSTER_AVAILABLE]`

## Swarm Configuration & Anti-Drift

- ALWAYS use hierarchical topology for coding swarms
- Keep maxAgents at 6-8 for tight coordination
- Use specialized strategy for clear role boundaries
- Use `raft` consensus for hive-mind (leader maintains authoritative state)
- Run frequent checkpoints via `post-task` hooks
- Keep shared memory namespace for all agents

```bash
npx @claude-flow/cli@latest swarm init --topology hierarchical --max-agents 8 --strategy specialized
```

## Swarm Execution Rules

- ALWAYS use `run_in_background: true` for all agent Task calls
- ALWAYS put ALL agent Task calls in ONE message for parallel execution
- After spawning, STOP — do NOT add more tool calls or check status
- Never poll TaskOutput or check swarm status — trust agents to return
- When agent results arrive, review ALL results before proceeding

## V3 CLI Commands

### Core Commands

| Command | Subcommands | Description |
|---------|-------------|-------------|
| `init` | 4 | Project initialization |
| `agent` | 8 | Agent lifecycle management |
| `swarm` | 6 | Multi-agent swarm coordination |
| `memory` | 11 | AgentDB memory with HNSW search |
| `task` | 6 | Task creation and lifecycle |
| `session` | 7 | Session state management |
| `hooks` | 17 | Self-learning hooks + 12 workers |
| `hive-mind` | 6 | Byzantine fault-tolerant consensus |

### Quick CLI Examples

```bash
npx @claude-flow/cli@latest init --wizard
npx @claude-flow/cli@latest agent spawn -t coder --name my-coder
npx @claude-flow/cli@latest swarm init --v3-mode
npx @claude-flow/cli@latest memory search --query "authentication patterns"
npx @claude-flow/cli@latest doctor --fix
```

## Available Agents (60+ Types)

### Core Development
`coder`, `reviewer`, `tester`, `planner`, `researcher`

### Specialized
`security-architect`, `security-auditor`, `memory-specialist`, `performance-engineer`

### Swarm Coordination
`hierarchical-coordinator`, `mesh-coordinator`, `adaptive-coordinator`

### GitHub & Repository
`pr-manager`, `code-review-swarm`, `issue-tracker`, `release-manager`

### SPARC Methodology
`sparc-coord`, `sparc-coder`, `specification`, `pseudocode`, `architecture`

## Memory Commands Reference

```bash
# Store (REQUIRED: --key, --value; OPTIONAL: --namespace, --ttl, --tags)
npx @claude-flow/cli@latest memory store --key "pattern-auth" --value "JWT with refresh" --namespace patterns

# Search (REQUIRED: --query; OPTIONAL: --namespace, --limit, --threshold)
npx @claude-flow/cli@latest memory search --query "authentication patterns"

# List (OPTIONAL: --namespace, --limit)
npx @claude-flow/cli@latest memory list --namespace patterns --limit 10

# Retrieve (REQUIRED: --key; OPTIONAL: --namespace)
npx @claude-flow/cli@latest memory retrieve --key "pattern-auth" --namespace patterns
```

## Quick Setup

```bash
claude mcp add claude-flow -- npx -y @claude-flow/cli@latest
npx @claude-flow/cli@latest daemon start
npx @claude-flow/cli@latest doctor --fix
```

## Claude Code vs CLI Tools

- Claude Code's Task tool handles ALL execution: agents, file ops, code generation, git
- CLI tools handle coordination via Bash: swarm init, memory, hooks, routing
- NEVER use CLI tools as a substitute for Task tool agents

## Support

- Documentation: https://github.com/ruvnet/claude-flow
- Issues: https://github.com/ruvnet/claude-flow/issues

## Bettingbot Project

### What This Project Is

A Python-based Discord betting bot where server members earn virtual points and spend them on two types of betting:
1. **Custom bets** — any server member creates an arbitrary multi-outcome parimutuel bet (e.g. "Who wins the game?"), others wager points on outcomes, and the creator resolves the winner.
2. **Horse races** — simulated races with 4–6 randomly selected horses, a 60-second betting window, animated mid-race progress (via message edits), and parimutuel payouts.

Points are isolated per Discord server (guild). New users start with 1,000 points.

### Entry Point

`main.py` — creates the `discord.Bot` instance, calls `database.setup_db()`, loads all four cogs, then starts the bot via `asyncio.run(main())`.

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
├── database.py       # SQLite helpers: setup_db, get_user_points, update_points
│                     #   Tables: users, bets, bet_options, wagers
├── helpers.py        # Shared utilities: info_embed, error_embed, get_reply_or_cancel
├── cogs/
│   ├── economy.py    # !balance, !daily, !leaderboard
│   ├── betting.py    # !createbet, !bets, !bet, !resolve
│   ├── misc.py       # !help (custom help command)
│   └── horserace.py  # !race, !racebet — in-memory race state, simulation, payouts
└── requirements.txt  # discord.py, python-dotenv, aiohttp (transitive)
```

### Coding Conventions

- Every cog is a `commands.Cog` subclass with `async def setup(bot)` at the bottom
- All user-facing responses use Discord embeds via `info_embed` / `error_embed` from `helpers.py`
- Points are always read/written through `get_user_points(user_id, guild_id)` / `update_points(user_id, guild_id, new_total)`
- Multi-step interactive input uses `get_reply_or_cancel(bot, ctx, prompt)` which handles timeouts and `cancel`
- Discord IDs are stored as `TEXT` in SQLite and always cast via `str()`
- Bot prefix is `!`; `help_command=None` disables the default help in favour of the custom `!help`

### Known Incomplete Areas & Technical Debt

| Issue | Location | Notes |
|-------|----------|-------|
| Module-level SQLite connection (`conn`, `c`) shared across cogs | `database.py:3` | Not thread-safe; fine for single-process but fragile under concurrent writes |
| `economy.py` imports `c, conn` directly for raw SQL | `cogs/economy.py:5` | Leaks DB internals into cog layer; `daily` command bypasses `update_points` |
| Race state is in-memory only | `cogs/horserace.py:70` | Lost on bot restart; by design for now but prevents history/stats |
| No slash commands — only `!` prefix | all cogs | Discord is pushing apps toward slash commands |
| No guild guard — `ctx.guild` assumed not None | all cogs | Bot would crash if a user ran commands in a DM |
| Only the bet creator can resolve a bet | `cogs/betting.py:297` | No admin/moderator override |
| Race entry odds are weight-based; actual payout is parimutuel | `cogs/horserace.py:103` | Displayed odds at race start are approximations |
| No per-user stats, bet history, or win rate tracking | `database.py` | Users can only see current balance |

### Planned Features

- **Leaderboards and user stats** — `!stats [@user]` showing total wagered, win rate, bets created/won, races entered
- **Bet history** — `!history` listing past bets a user participated in with outcomes and payouts
- **Slash commands** — migrate to `discord.app_commands` alongside or replacing prefix commands
- **Admin commands** — force-close bets, adjust points, mod overrides for resolution
