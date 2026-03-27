# AWS Deployment Design — Bettingbot

**Date:** 2026-03-27
**Status:** Approved

## Overview

Migrate bettingbot from a Raspberry Pi running SQLite to a production AWS deployment using ECS Fargate, RDS Postgres, GitHub Actions CI/CD, Terraform IaC, Secrets Manager, and CloudWatch. Goal is maximum employer signal for an active job search.

## Branch Strategy

- `main` — AWS production deployment, triggers GitHub Actions on push
- `pi` — Raspberry Pi / SQLite setup, preserved as-is, runs manually

## Architecture

```
GitHub (main branch)
    │
    ▼
GitHub Actions
    ├── Job 1: test  → pytest (blocks deploy on failure)
    └── Job 2: deploy
          ├── Build Docker image
          ├── Push to ECR (tagged with git commit SHA)
          └── Force redeploy ECS service

ECS Fargate (serverless container)
    └── bettingbot container
          ├── DISCORD_TOKEN  ← Secrets Manager
          ├── DATABASE_URL   ← Secrets Manager
          └── stdout logs    → CloudWatch Log Group

RDS Postgres (db.t3.micro, free tier)
    └── tables: users, bets, bet_options, wagers

CloudWatch
    ├── Log group: /ecs/bettingbot
    └── Alarm: container exit → SNS → email
```

## Components

### 1. Dockerfile

New file at repo root. Builds the bot into a Docker image:
- Base image: `python:3.11-slim`
- Copies source, installs `requirements.txt`
- Entrypoint: `python main.py`

### 2. GitHub Actions (`/.github/workflows/deploy.yml`)

Triggers on push to `main`. Two jobs:

**test:**
- Install dependencies
- Run `pytest tests/`
- Failure blocks deploy

**deploy** (runs only if test passes):
- Configure AWS credentials from GitHub Secrets
- Log in to ECR
- Build and push Docker image tagged with `$GITHUB_SHA`
- Update ECS service to force new deployment

GitHub Secrets required (set in repo settings, never in code):
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`

### 3. Terraform (`/terraform/`)

All infrastructure defined as code. Running `terraform apply` builds everything from scratch.

| File | What it creates |
|------|----------------|
| `main.tf` | AWS provider config, Terraform backend (S3) |
| `variables.tf` | Input vars: region, app name, db password, alert email |
| `outputs.tf` | ECR URL, RDS endpoint, ECS cluster name |
| `vpc.tf` | VPC, public subnet (ECS), private subnet (RDS), internet gateway |
| `ecr.tf` | ECR repository for Docker images |
| `ecs.tf` | Fargate cluster, task definition (512 CPU / 1024MB RAM), service |
| `rds.tf` | db.t3.micro Postgres, automated backups, private subnet |
| `secrets.tf` | Secrets Manager entries for DISCORD_TOKEN and DATABASE_URL |
| `iam.tf` | ECS task role: ECR pull, Secrets Manager read, CloudWatch write |
| `cloudwatch.tf` | Log group, crash alarm, SNS email topic |

**Networking:**
- ECS container in public subnet (needs outbound internet to reach Discord API)
- RDS in private subnet (no public internet access)
- Security group: ECS → RDS on port 5432 only

**Free tier coverage (12 months):**
- ECS Fargate: 750 vCPU-hours + 750 GB-hours/month — covers 24/7 single container
- RDS db.t3.micro: 750 hours/month — covers 24/7
- Secrets Manager: ~$0.80/month (2 secrets)
- Estimated cost: $1–2/month in year 1

### 4. Code Changes

**`requirements.txt`** — add `psycopg2-binary`

**`database.py`** — swap SQLite for Postgres:
- Replace `sqlite3` with `psycopg2`
- Update connection to use `os.environ["DATABASE_URL"]`
- Update placeholder syntax: `?` → `%s`
- Update upsert syntax: `INSERT OR IGNORE` → `INSERT ... ON CONFLICT DO NOTHING`
- Update `AUTOINCREMENT` → `SERIAL` in schema creation

**`logger.py`** (new, in repo root) — thin wrapper around Python `logging`:
- Outputs structured JSON logs
- Imported by cogs that need logging

**`main.py`** — replace `print()` with `logger.info()`

### 5. Data Migration (one-time)

Migrate existing SQLite data from Pi to RDS before shutting down the Pi bot.

**Script: `scripts/migrate_sqlite_to_postgres.py`**
- Reads from local SQLite file (`betting.db`)
- Connects to RDS via `DATABASE_URL` env var
- Inserts all rows from: `users`, `bets`, `bet_options`, `wagers`
- Handles SQLite→Postgres type differences (booleans, integers)
- Idempotent: safe to run multiple times (uses `ON CONFLICT DO NOTHING`)

**Migration sequence:**
1. Pi bot stays running during entire AWS setup
2. Once AWS bot is live and verified working, run migration script
3. Shut down Pi bot
4. Verify data in RDS matches Pi SQLite

### 6. Observability

**Logging:**
- All cogs import `logger.py`
- Key events logged: bot ready, command invoked, bet resolved, race started, errors
- Logs stream automatically to CloudWatch `/ecs/bettingbot` log group

**Alerting:**
- CloudWatch alarm: ECS task exit count > 0 in any 5-minute window
- Alarm triggers SNS topic → email notification
- Alert email set via Terraform variable (never hardcoded)

## Local Development

- `pi` branch: unchanged, uses SQLite + `.env`
- `main` branch local testing: `.env` with `DATABASE_URL=postgresql://localhost:5432/bettingbot_dev`
- Run local Postgres via Docker: `docker run -e POSTGRES_PASSWORD=dev -p 5432:5432 postgres`

## Security

- `.env` remains gitignored
- No secrets in Terraform files — sensitive values passed as variables at apply time
- Terraform state stored in S3 (not locally) — state may contain sensitive values, S3 bucket has versioning + encryption enabled
- ECS task IAM role follows least privilege — only permissions the container actually needs
- RDS not publicly accessible — only reachable from ECS security group

## Implementation Order

1. Create `Dockerfile`, verify bot runs in container locally
2. Write Terraform, run `terraform apply` to provision AWS infrastructure
3. Set secret values in Secrets Manager via AWS CLI
4. Set GitHub Secrets in repo settings
5. Write GitHub Actions workflow
6. Update `database.py` for Postgres, update `requirements.txt`
7. Write and run data migration script
8. Push to `main`, verify pipeline runs end-to-end
9. Verify bot is live in Discord
10. Shut down Pi bot
