# Bettingbot

Discord betting bot with horse races, custom multi-outcome bets, and virtual points. Deployed on AWS ECS Fargate with RDS Postgres and a GitHub Actions CI/CD pipeline.

## How it works

The bot runs as a single async Python process on ECS Fargate, connected to RDS PostgreSQL. All Discord events are handled concurrently through discord.py's async event loop - users can place bets, trigger races, and check balances simultaneously without blocking each other.

A few decisions behind the architecture:

**ECS Fargate over a simpler host (EC2, Railway, etc.)** - I wanted to learn AWS properly and get automatic rolling deploys without downtime. Fargate also handles restarts if the container crashes, which matters for something that's supposed to be always-on.

**RDS PostgreSQL over SQLite** - SQLite works fine locally, but concurrent writes under load cause locking issues. Moving to Postgres decoupled the database from the container lifecycle and made the system more reliable when multiple users interact at the same time.

**Secrets Manager over environment variables in the task definition** - Discord token and DB credentials are pulled at runtime from AWS Secrets Manager. They never touch the image or the repo.

**CI/CD that gates on tests** - The GitHub Actions pipeline runs pytest first. If tests fail, nothing builds or deploys. Broken code doesn't reach production.

## Commands

| Command | Description |
|---|---|
| `!balance` | Show your points |
| `!daily` | Claim 100 points (24h cooldown) |
| `!leaderboard` | Top 10 users by points in the server |
| `!createbet` | Create a multi-outcome parimutuel bet |
| `!bets` | List all open bets with odds |
| `!bet [id] [outcome] [amount]` | Place a wager on an open bet |
| `!resolve [bet_id] [outcome]` | Resolve a bet you created |
| `!race` | Start a horse race with a 60s betting window |
| `!racebet <number> <amount>` | Bet on a horse during a race |
| `!setracechannel [#channel]` | Set the channel for the daily big race |
| `!racenotify` | Toggle pings for the daily big race |
| `!racebetbig <number> <amount>` | Bet carats on the daily big race |
| `!help` | Show all commands |

## Stack

- **Runtime** — Python 3.11, discord.py 2.x
- **Database** — Postgres (prod) / SQLite (local)
- **Infrastructure** — AWS ECS Fargate, RDS, ECR, Secrets Manager, CloudWatch
- **IaC** — Terraform
- **CI/CD** — GitHub Actions (test → build → deploy on push to `main`)

## Running locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "DISCORD_TOKEN=your_token_here" > .env
python main.py
```

Set `DATABASE_URL` in `.env` to use Postgres. Without it, the bot defaults to SQLite at `data/betting.db`.

## Running tests

```bash
source venv/bin/activate
python3 -m pytest tests/ -v
```
