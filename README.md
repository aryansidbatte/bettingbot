# Bettingbot

Discord betting bot with horse races, custom multi-outcome bets, and virtual points. Deployed on AWS ECS Fargate with RDS Postgres and a GitHub Actions CI/CD pipeline.

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

## Stack

- **Runtime** — Python 3.11, discord.py 2.x
- **Database** — Postgres (prod) / SQLite (local)
- **Infrastructure** — AWS ECS Fargate, RDS, ECR, Secrets Manager, CloudWatch
- **IaC** — Terraform
- **CI/CD** — GitHub Actions (test → build → deploy on push to `main`)
