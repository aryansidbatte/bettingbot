# AWS Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy bettingbot to AWS ECS Fargate with RDS Postgres, GitHub Actions CI/CD, Terraform IaC, Secrets Manager, and CloudWatch — migrating from Raspberry Pi SQLite.

**Architecture:** ECS Fargate runs the bot as a Docker container in a public subnet; RDS Postgres lives in a private subnet only reachable from ECS. GitHub Actions tests, builds, and deploys on every push to `main`. All infrastructure is defined in Terraform and provisioned with a single `terraform apply`.

**Tech Stack:** Python 3.11, psycopg2, Docker, Terraform 1.x, GitHub Actions, AWS (ECS Fargate, ECR, RDS Postgres, Secrets Manager, CloudWatch, EventBridge, SNS, VPC, IAM)

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `Dockerfile` | Build bot into Docker image |
| Create | `.dockerignore` | Exclude venv, .env, tests from image |
| Create | `.github/workflows/deploy.yml` | CI/CD: test → build → push ECR → deploy ECS |
| Create | `terraform/main.tf` | AWS provider + S3 backend config |
| Create | `terraform/variables.tf` | Input variables (region, db_password, etc.) |
| Create | `terraform/outputs.tf` | Print ECR URL, ECS names, RDS endpoint after apply |
| Create | `terraform/vpc.tf` | VPC, subnets, internet gateway, security groups |
| Create | `terraform/ecr.tf` | ECR repository for Docker images |
| Create | `terraform/iam.tf` | ECS execution role with ECR + Secrets Manager permissions |
| Create | `terraform/rds.tf` | RDS Postgres db.t3.micro in private subnet |
| Create | `terraform/secrets.tf` | Secrets Manager entries for DISCORD_TOKEN + DATABASE_URL |
| Create | `terraform/ecs.tf` | Fargate cluster, task definition, service |
| Create | `terraform/cloudwatch.tf` | Log group, EventBridge crash alarm, SNS email topic |
| Create | `logger.py` | Structured JSON logging wrapper, imported by main.py |
| Create | `scripts/migrate_sqlite_to_postgres.py` | One-time data migration from Pi SQLite to RDS |
| Modify | `database.py` | Support Postgres (psycopg2) when DATABASE_URL is set, SQLite otherwise |
| Modify | `requirements.txt` | Add psycopg2-binary |
| Modify | `main.py` | Replace print() with logger calls |

---

## Phase 1: AWS Account & Tools

### Task 1: Create AWS Account

- [ ] **Step 1: Sign up for AWS**

  Go to https://aws.amazon.com and click **Create an AWS Account**.
  - Email: use a real email you check (alerts will go here)
  - Account name: anything (e.g. "bettingbot-dev")
  - Choose **Personal** account type
  - Enter payment card (required even for free tier — you won't be charged if you stay within limits)
  - Select **Basic support** (free)
  - Verify your email and phone number

- [ ] **Step 2: Enable MFA on root account**

  In the AWS Console top-right, click your account name → **Security credentials** → **Assign MFA device**. Use an authenticator app. This protects your account.

- [ ] **Step 3: Create an IAM user for all CLI/Terraform work**

  Never use your root account for day-to-day work. In the AWS Console:
  - Search for **IAM** → **Users** → **Create user**
  - Username: `bettingbot-admin`
  - Check **Provide user access to the AWS Management Console** → No (CLI only)
  - Click **Next** → **Attach policies directly** → search and select **AdministratorAccess**
  - Click **Create user**

- [ ] **Step 4: Create access keys for the IAM user**

  - Click on the `bettingbot-admin` user → **Security credentials** tab
  - Under **Access keys** → **Create access key**
  - Use case: **Command Line Interface (CLI)**
  - Click through warnings → **Create access key**
  - **Download the CSV file now** — you cannot view the secret key again after this screen

---

### Task 2: Install Tools

- [ ] **Step 1: Install AWS CLI**

  On Mac:
  ```bash
  brew install awscli
  aws --version
  # Expected: aws-cli/2.x.x ...
  ```

- [ ] **Step 2: Configure AWS CLI with your IAM user credentials**

  ```bash
  aws configure
  ```
  Enter when prompted:
  - AWS Access Key ID: (from the CSV you downloaded)
  - AWS Secret Access Key: (from the CSV)
  - Default region name: `us-west-1`
  - Default output format: `json`

  Verify it works:
  ```bash
  aws sts get-caller-identity
  # Expected: JSON with your account ID and user ARN
  ```

- [ ] **Step 3: Install Terraform**

  On Mac:
  ```bash
  brew tap hashicorp/tap
  brew install hashicorp/tap/terraform
  terraform --version
  # Expected: Terraform v1.x.x
  ```

- [ ] **Step 4: Install Docker Desktop**

  Download from https://www.docker.com/products/docker-desktop/ and install. Start Docker Desktop before continuing.

  ```bash
  docker --version
  # Expected: Docker version 27.x.x ...
  ```

---

### Task 3: Create S3 Bucket for Terraform State

Terraform needs somewhere to store its state file. S3 is the standard choice. This bucket must exist before `terraform init`.

- [ ] **Step 1: Create the S3 bucket**

  Replace `YOUR_ACCOUNT_ID` with your 12-digit AWS account ID (visible in `aws sts get-caller-identity`):

  ```bash
  aws s3api create-bucket --bucket bettingbot-terraform-state-YOUR_ACCOUNT_ID --region us-west-1 --create-bucket-configuration LocationConstraint=us-west-1
  ```

  Example if your account ID is `123456789012`:
  ```bash
  aws s3api create-bucket --bucket bettingbot-terraform-state-123456789012 --region us-west-1 --create-bucket-configuration LocationConstraint=us-west-1
  ```

- [ ] **Step 2: Enable versioning on the bucket**

  ```bash
  aws s3api put-bucket-versioning --bucket bettingbot-terraform-state-YOUR_ACCOUNT_ID --versioning-configuration Status=Enabled
  ```

- [ ] **Step 3: Note your bucket name**

  You will use it in Task 4 when writing `terraform/main.tf`. Write it down:
  ```
  Bucket name: bettingbot-terraform-state-____________
  ```

---

## Phase 2: Containerize

### Task 4: Write Dockerfile and Test Locally

- [ ] **Step 1: Create `.dockerignore`**

  ```
  venv/
  .env
  .git/
  __pycache__/
  *.pyc
  *.pyo
  tests/
  data/betting.db
  docs/
  terraform/
  scripts/
  ```

- [ ] **Step 2: Create `Dockerfile`**

  ```dockerfile
  FROM python:3.11-slim

  WORKDIR /app

  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt

  COPY . .

  CMD ["python", "main.py"]
  ```

- [ ] **Step 3: Build the image locally to verify it works**

  ```bash
  docker build -t bettingbot:local .
  ```

  Expected: `Successfully built ...` with no errors.

  **Note:** If you see `ERROR: Could not find a version of audioop-lts`, remove it from `requirements.txt` — it requires Python 3.13+ and is not needed on 3.11. If you see import errors or missing files, fix them before continuing.

- [ ] **Step 4: Commit**

  ```bash
  git add Dockerfile .dockerignore
  git commit -m "feat: add Dockerfile for containerized deployment"
  ```

---

## Phase 3: Terraform Infrastructure

### Task 5: Write `terraform/main.tf` and `terraform/variables.tf`

- [ ] **Step 1: Create the `terraform/` directory and write `terraform/main.tf`**

  Replace `bettingbot-terraform-state-YOUR_ACCOUNT_ID` with your actual bucket name from Task 3.

  ```hcl
  terraform {
    required_providers {
      aws = {
        source  = "hashicorp/aws"
        version = "~> 5.0"
      }
    }

    backend "s3" {
      bucket = "bettingbot-terraform-state-YOUR_ACCOUNT_ID"
      key    = "terraform.tfstate"
      region = "us-west-1"
    }
  }

  provider "aws" {
    region = var.aws_region
  }
  ```

- [ ] **Step 2: Write `terraform/variables.tf`**

  ```hcl
  variable "aws_region" {
    description = "AWS region to deploy into"
    default     = "us-west-1"
  }

  variable "app_name" {
    description = "Name prefix for all resources"
    default     = "bettingbot"
  }

  variable "db_password" {
    description = "Password for the RDS Postgres database"
    sensitive   = true
  }

  variable "discord_token" {
    description = "Discord bot token"
    sensitive   = true
  }

  variable "alert_email" {
    description = "Email address to receive crash alerts"
  }
  ```

- [ ] **Step 3: Create `terraform/terraform.tfvars`** (this file is gitignored — never commit it)

  ```hcl
  db_password   = "PickAStrongPasswordHere123!"
  discord_token = "your-discord-token-here"
  alert_email   = "your-email@example.com"
  ```

- [ ] **Step 4: Add `terraform.tfvars` to `.gitignore`**

  Open `.gitignore` and add:
  ```
  terraform/terraform.tfvars
  terraform/.terraform/
  terraform/*.tfstate
  terraform/*.tfstate.backup
  ```

---

### Task 6: Write `terraform/vpc.tf`

- [ ] **Step 1: Write `terraform/vpc.tf`**

  ```hcl
  resource "aws_vpc" "main" {
    cidr_block           = "10.0.0.0/16"
    enable_dns_hostnames = true
    tags = { Name = "${var.app_name}-vpc" }
  }

  # ECS lives here — needs internet access to reach Discord API
  resource "aws_subnet" "public_a" {
    vpc_id                  = aws_vpc.main.id
    cidr_block              = "10.0.1.0/24"
    availability_zone       = "${var.aws_region}a"
    map_public_ip_on_launch = true
    tags = { Name = "${var.app_name}-public-a" }
  }

  # RDS lives here — no public internet access
  resource "aws_subnet" "private_a" {
    vpc_id            = aws_vpc.main.id
    cidr_block        = "10.0.2.0/24"
    availability_zone = "${var.aws_region}a"
    tags = { Name = "${var.app_name}-private-a" }
  }

  # RDS subnet group requires 2 AZs
  resource "aws_subnet" "private_b" {
    vpc_id            = aws_vpc.main.id
    cidr_block        = "10.0.3.0/24"
    availability_zone = "${var.aws_region}c"
    tags = { Name = "${var.app_name}-private-b" }
  }

  resource "aws_internet_gateway" "main" {
    vpc_id = aws_vpc.main.id
    tags = { Name = "${var.app_name}-igw" }
  }

  resource "aws_route_table" "public" {
    vpc_id = aws_vpc.main.id
    route {
      cidr_block = "0.0.0.0/0"
      gateway_id = aws_internet_gateway.main.id
    }
    tags = { Name = "${var.app_name}-public-rt" }
  }

  resource "aws_route_table_association" "public_a" {
    subnet_id      = aws_subnet.public_a.id
    route_table_id = aws_route_table.public.id
  }

  # ECS security group — allows all outbound, no inbound (bot initiates connections)
  resource "aws_security_group" "ecs" {
    name   = "${var.app_name}-ecs-sg"
    vpc_id = aws_vpc.main.id

    egress {
      from_port   = 0
      to_port     = 0
      protocol    = "-1"
      cidr_blocks = ["0.0.0.0/0"]
    }

    tags = { Name = "${var.app_name}-ecs-sg" }
  }

  # RDS security group — only accepts connections from ECS
  resource "aws_security_group" "rds" {
    name   = "${var.app_name}-rds-sg"
    vpc_id = aws_vpc.main.id

    ingress {
      from_port       = 5432
      to_port         = 5432
      protocol        = "tcp"
      security_groups = [aws_security_group.ecs.id]
    }

    tags = { Name = "${var.app_name}-rds-sg" }
  }
  ```

---

### Task 7: Write `terraform/ecr.tf` and `terraform/iam.tf`

- [ ] **Step 1: Write `terraform/ecr.tf`**

  ```hcl
  resource "aws_ecr_repository" "bettingbot" {
    name                 = var.app_name
    image_tag_mutability = "MUTABLE"

    image_scanning_configuration {
      scan_on_push = true
    }

    tags = { Name = var.app_name }
  }

  # Keep only the 5 most recent images to avoid storage costs
  resource "aws_ecr_lifecycle_policy" "bettingbot" {
    repository = aws_ecr_repository.bettingbot.name

    policy = jsonencode({
      rules = [{
        rulePriority = 1
        description  = "Keep last 5 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = { type = "expire" }
      }]
    })
  }
  ```

- [ ] **Step 2: Write `terraform/iam.tf`**

  ```hcl
  data "aws_iam_policy_document" "ecs_assume_role" {
    statement {
      actions = ["sts:AssumeRole"]
      principals {
        type        = "Service"
        identifiers = ["ecs-tasks.amazonaws.com"]
      }
    }
  }

  # Execution role: used by ECS agent to pull images and inject secrets at startup
  resource "aws_iam_role" "ecs_execution" {
    name               = "${var.app_name}-ecs-execution-role"
    assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
  }

  resource "aws_iam_role_policy_attachment" "ecs_execution_base" {
    role       = aws_iam_role.ecs_execution.name
    policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
  }

  resource "aws_iam_role_policy" "ecs_execution_secrets" {
    name = "${var.app_name}-execution-secrets"
    role = aws_iam_role.ecs_execution.id

    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [{
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = [
          aws_secretsmanager_secret.discord_token.arn,
          aws_secretsmanager_secret.database_url.arn
        ]
      }]
    })
  }
  ```

---

### Task 8: Write `terraform/rds.tf` and `terraform/secrets.tf`

- [ ] **Step 1: Write `terraform/rds.tf`**

  ```hcl
  resource "aws_db_subnet_group" "main" {
    name       = "${var.app_name}-db-subnet-group"
    subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]
    tags = { Name = "${var.app_name}-db-subnet-group" }
  }

  resource "aws_db_instance" "main" {
    identifier        = "${var.app_name}-db"
    engine            = "postgres"
    engine_version    = "15"
    instance_class    = "db.t3.micro"
    allocated_storage = 20

    db_name  = "bettingbot"
    username = "bettingbot"
    password = var.db_password

    db_subnet_group_name   = aws_db_subnet_group.main.name
    vpc_security_group_ids = [aws_security_group.rds.id]

    publicly_accessible     = false
    skip_final_snapshot     = true
    backup_retention_period = 0

    tags = { Name = "${var.app_name}-db" }
  }
  ```

- [ ] **Step 2: Write `terraform/secrets.tf`**

  ```hcl
  resource "aws_secretsmanager_secret" "discord_token" {
    name = "${var.app_name}/discord-token"
    tags = { Name = "${var.app_name}-discord-token" }
  }

  resource "aws_secretsmanager_secret_version" "discord_token" {
    secret_id     = aws_secretsmanager_secret.discord_token.id
    secret_string = var.discord_token
  }

  resource "aws_secretsmanager_secret" "database_url" {
    name = "${var.app_name}/database-url"
    tags = { Name = "${var.app_name}-database-url" }
  }

  resource "aws_secretsmanager_secret_version" "database_url" {
    secret_id     = aws_secretsmanager_secret.database_url.id
    secret_string = "postgresql://bettingbot:${var.db_password}@${aws_db_instance.main.endpoint}/bettingbot"
  }
  ```

---

### Task 9: Write `terraform/ecs.tf`

- [ ] **Step 1: Write `terraform/ecs.tf`**

  ```hcl
  resource "aws_ecs_cluster" "main" {
    name = var.app_name
    tags = { Name = var.app_name }
  }

  resource "aws_ecs_task_definition" "bettingbot" {
    family                   = var.app_name
    requires_compatibilities = ["FARGATE"]
    network_mode             = "awsvpc"
    cpu                      = 256
    memory                   = 512
    execution_role_arn       = aws_iam_role.ecs_execution.arn

    container_definitions = jsonencode([{
      name  = var.app_name
      image = "${aws_ecr_repository.bettingbot.repository_url}:latest"

      secrets = [
        {
          name      = "DISCORD_TOKEN"
          valueFrom = aws_secretsmanager_secret.discord_token.arn
        },
        {
          name      = "DATABASE_URL"
          valueFrom = aws_secretsmanager_secret.database_url.arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/${var.app_name}"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }])
  }

  resource "aws_ecs_service" "bettingbot" {
    name            = var.app_name
    cluster         = aws_ecs_cluster.main.id
    task_definition = aws_ecs_task_definition.bettingbot.arn
    desired_count   = 1
    launch_type     = "FARGATE"

    network_configuration {
      subnets          = [aws_subnet.public_a.id]
      security_groups  = [aws_security_group.ecs.id]
      assign_public_ip = true
    }

    # GitHub Actions updates the task definition — Terraform must not overwrite it
    lifecycle {
      ignore_changes = [task_definition]
    }
  }
  ```

---

### Task 10: Write `terraform/cloudwatch.tf` and `terraform/outputs.tf`

- [ ] **Step 1: Write `terraform/cloudwatch.tf`**

  ```hcl
  resource "aws_cloudwatch_log_group" "ecs" {
    name              = "/ecs/${var.app_name}"
    retention_in_days = 30
    tags = { Name = "${var.app_name}-logs" }
  }

  resource "aws_sns_topic" "alerts" {
    name = "${var.app_name}-alerts"
  }

  resource "aws_sns_topic_subscription" "email" {
    topic_arn = aws_sns_topic.alerts.arn
    protocol  = "email"
    endpoint  = var.alert_email
  }

  # Alert when the bot container stops unexpectedly
  resource "aws_cloudwatch_event_rule" "ecs_task_stopped" {
    name        = "${var.app_name}-task-stopped"
    description = "Fires when bettingbot ECS task transitions to STOPPED"

    event_pattern = jsonencode({
      source      = ["aws.ecs"]
      "detail-type" = ["ECS Task State Change"]
      detail = {
        clusterArn = [aws_ecs_cluster.main.arn]
        lastStatus = ["STOPPED"]
      }
    })
  }

  resource "aws_cloudwatch_event_target" "sns" {
    rule      = aws_cloudwatch_event_rule.ecs_task_stopped.name
    target_id = "SendToSNS"
    arn       = aws_sns_topic.alerts.arn
  }

  resource "aws_sns_topic_policy" "allow_events" {
    arn = aws_sns_topic.alerts.arn
    policy = jsonencode({
      Version = "2012-10-17"
      Statement = [{
        Effect    = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action    = "SNS:Publish"
        Resource  = aws_sns_topic.alerts.arn
      }]
    })
  }
  ```

- [ ] **Step 2: Write `terraform/outputs.tf`**

  ```hcl
  output "ecr_repository_url" {
    value       = aws_ecr_repository.bettingbot.repository_url
    description = "ECR URL — used in GitHub Actions to push images"
  }

  output "ecs_cluster_name" {
    value = aws_ecs_cluster.main.name
  }

  output "ecs_service_name" {
    value = aws_ecs_service.bettingbot.name
  }

  output "rds_endpoint" {
    value       = aws_db_instance.main.endpoint
    description = "RDS host:port — use this to connect to Postgres from your laptop for migration"
  }
  ```

---

### Task 11: Run Terraform

- [ ] **Step 1: Initialize Terraform**

  ```bash
  cd terraform
  terraform init
  ```

  Expected output ends with:
  ```
  Terraform has been successfully initialized!
  ```

- [ ] **Step 2: Preview what Terraform will create**

  ```bash
  terraform plan -var-file=terraform.tfvars
  ```

  Expected: a list of ~20-25 resources to be created, ending with:
  ```
  Plan: 25 to add, 0 to change, 0 to destroy.
  ```

  Read through the list — every resource name should match the file map above.

- [ ] **Step 3: Apply (this will take ~10 minutes — RDS takes longest)**

  ```bash
  terraform apply -var-file=terraform.tfvars
  ```

  Type `yes` when prompted. Wait for completion.

  Expected ending:
  ```
  Apply complete! Resources: 25 added, 0 changed, 0 destroyed.

  Outputs:
  ecr_repository_url = "123456789012.dkr.ecr.us-west-1.amazonaws.com/bettingbot"
  ecs_cluster_name   = "bettingbot"
  ecs_service_name   = "bettingbot"
  rds_endpoint       = "bettingbot-db.xxxx.us-west-1.rds.amazonaws.com:5432"
  ```

  **Copy these output values — you need them in later tasks.**

- [ ] **Step 4: Confirm your alert email subscription**

  AWS sent a confirmation email to your `alert_email`. Open it and click **Confirm subscription** — otherwise crash alerts won't arrive.

- [ ] **Step 5: Return to project root and commit Terraform files**

  ```bash
  cd ..
  git add terraform/
  git commit -m "feat: add Terraform infrastructure (ECS Fargate, RDS, ECR, VPC, CloudWatch)"
  ```

---

## Phase 4: App Code Changes

### Task 12: Update `database.py` for Postgres Compatibility

`database.py` currently uses SQLite unconditionally. We make it use Postgres when `DATABASE_URL` is set (production), and fall back to SQLite when it's not (tests, local dev on `pi` branch). This keeps all existing tests passing without changes.

- [ ] **Step 1: Run tests to confirm they currently pass**

  ```bash
  source venv/bin/activate && python3 -m pytest tests/ -v
  ```

  Expected: all tests pass. This is your baseline.

- [ ] **Step 2: Replace the top of `database.py`** (lines 1–9)

  Old:
  ```python
  import sqlite3
  import os
  from datetime import datetime

  _db_dir = os.path.join(os.path.dirname(__file__), "data")
  os.makedirs(_db_dir, exist_ok=True)
  _db_path = os.path.join(_db_dir, "betting.db")
  conn = sqlite3.connect(_db_path)
  c = conn.cursor()
  ```

  New:
  ```python
  import os
  from datetime import datetime

  DATABASE_URL = os.environ.get("DATABASE_URL", "")

  if DATABASE_URL.startswith("postgres"):
      import psycopg2
      conn = psycopg2.connect(DATABASE_URL)
      _PH = "%s"
      _is_postgres = True
  else:
      import sqlite3
      _db_dir = os.path.join(os.path.dirname(__file__), "data")
      os.makedirs(_db_dir, exist_ok=True)
      _db_path = os.path.join(_db_dir, "betting.db")
      conn = sqlite3.connect(_db_path)
      _PH = "?"
      _is_postgres = False

  c = conn.cursor()
  ```

- [ ] **Step 3: Replace `setup_db()` entirely**

  ```python
  def setup_db():
      if _is_postgres:
          c.execute("""
          CREATE TABLE IF NOT EXISTS users (
              user_id    TEXT NOT NULL,
              guild_id   TEXT NOT NULL,
              monies     INTEGER NOT NULL DEFAULT 1000,
              carats     INTEGER NOT NULL DEFAULT 0,
              vc_minutes INTEGER NOT NULL DEFAULT 0,
              last_daily TEXT,
              PRIMARY KEY (user_id, guild_id)
          )
          """)
          c.execute("""
          CREATE TABLE IF NOT EXISTS bets (
              bet_id      SERIAL PRIMARY KEY,
              guild_id    TEXT,
              creator_id  TEXT,
              description TEXT,
              status      TEXT DEFAULT 'open'
          )
          """)
          c.execute("""
          CREATE TABLE IF NOT EXISTS bet_options (
              option_id    SERIAL PRIMARY KEY,
              bet_id       INTEGER,
              name         TEXT,
              total_amount INTEGER DEFAULT 0
          )
          """)
          c.execute("""
          CREATE TABLE IF NOT EXISTS wagers (
              wager_id  SERIAL PRIMARY KEY,
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
      else:
          c.execute("""
          CREATE TABLE IF NOT EXISTS users (
              user_id    TEXT NOT NULL,
              guild_id   TEXT NOT NULL,
              monies     INTEGER NOT NULL DEFAULT 1000,
              carats     INTEGER NOT NULL DEFAULT 0,
              vc_minutes INTEGER NOT NULL DEFAULT 0,
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
          try:
              c.execute("ALTER TABLE users ADD COLUMN vc_minutes INTEGER NOT NULL DEFAULT 0")
          except Exception:
              conn.rollback()
      conn.commit()
  ```

- [ ] **Step 4: Replace all `?` placeholders in every query**

  In every function below `setup_db()`, replace every `"?"` with `_PH`. Do a global find-and-replace in `database.py` only:

  Find: `"?"`
  Replace with: `_PH`

  And replace `?,` with `{_PH},` in multi-placeholder strings. The pattern to use is an f-string:

  Example — `get_user_monies`:
  ```python
  def get_user_monies(user_id, guild_id):
      c.execute(
          f"SELECT monies FROM users WHERE user_id={_PH} AND guild_id={_PH}",
          (str(user_id), str(guild_id)),
      )
      result = c.fetchone()
      if result is None:
          c.execute(
              f"INSERT INTO users (user_id, guild_id, monies, carats, vc_minutes, last_daily) VALUES ({_PH},{_PH},{_PH},{_PH},{_PH},{_PH})",
              (str(user_id), str(guild_id), 1000, 0, 0, None),
          )
          conn.commit()
          return 1000
      return result[0]
  ```

  Apply the same `?` → `{_PH}` replacement to every function: `update_monies`, `get_user_carats`, `update_carats`, `get_vc_minutes`, `add_vc_minutes`, `add_daily_reward`, `get_race_channel`, `set_race_channel`, `get_all_race_configs`, `is_enrolled`, `toggle_enrollment`, `get_enrolled_users`.

  Also update `set_race_channel` — the multi-placeholder upsert:
  ```python
  def set_race_channel(guild_id, channel_id):
      c.execute(
          f"INSERT INTO race_config (guild_id, channel_id) VALUES ({_PH},{_PH}) "
          f"ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id",
          (str(guild_id), str(channel_id)),
      )
      conn.commit()
  ```

- [ ] **Step 5: Run tests to verify nothing broke**

  ```bash
  source venv/bin/activate && python3 -m pytest tests/ -v
  ```

  Expected: all tests still pass. Tests use SQLite (no `DATABASE_URL` set), so the existing `conftest.py` monkeypatching still works unchanged.

- [ ] **Step 6: Commit**

  ```bash
  git add database.py
  git commit -m "feat: support Postgres via DATABASE_URL env var, fall back to SQLite"
  ```

---

### Task 13: Fix Raw SQL Placeholders in `cogs/economy.py`

`economy.py` imports `c` and `conn` directly from `database.py` and runs its own raw SQL queries using `?` placeholders. These break in Postgres — the same `_PH` fix applies.

- [ ] **Step 1: Add `_PH` to the import line in `cogs/economy.py`**

  Old line 5:
  ```python
  from database import c, conn, get_user_monies, update_monies, add_daily_reward, get_user_carats
  ```

  New:
  ```python
  from database import c, conn, _PH, get_user_monies, update_monies, add_daily_reward, get_user_carats
  ```

- [ ] **Step 2: Fix the `leaderboard` query (line 26)**

  Old:
  ```python
  c.execute(
      "SELECT user_id, monies FROM users WHERE guild_id=? "
      "ORDER BY monies DESC LIMIT 10",
      (str(ctx.guild.id),),
  )
  ```

  New:
  ```python
  c.execute(
      f"SELECT user_id, monies FROM users WHERE guild_id={_PH} "
      "ORDER BY monies DESC LIMIT 10",
      (str(ctx.guild.id),),
  )
  ```

- [ ] **Step 3: Fix the `caratboard` query (line 55)**

  Old:
  ```python
  c.execute(
      "SELECT user_id, carats FROM users WHERE guild_id=? "
      "ORDER BY carats DESC LIMIT 10",
      (str(ctx.guild.id),),
  )
  ```

  New:
  ```python
  c.execute(
      f"SELECT user_id, carats FROM users WHERE guild_id={_PH} "
      "ORDER BY carats DESC LIMIT 10",
      (str(ctx.guild.id),),
  )
  ```

- [ ] **Step 4: Fix the `daily` query (line 88)**

  Old:
  ```python
  c.execute(
      "SELECT monies, last_daily FROM users WHERE user_id=? AND guild_id=?",
      (user_id, guild_id),
  )
  ```

  New:
  ```python
  c.execute(
      f"SELECT monies, last_daily FROM users WHERE user_id={_PH} AND guild_id={_PH}",
      (user_id, guild_id),
  )
  ```

- [ ] **Step 5: Fix the `forcedaily` query (line 124)**

  Old:
  ```python
  c.execute(
      "UPDATE users SET monies=monies+100, carats=carats+10 WHERE guild_id=?",
      (str(ctx.guild.id),),
  )
  ```

  New:
  ```python
  c.execute(
      f"UPDATE users SET monies=monies+100, carats=carats+10 WHERE guild_id={_PH}",
      (str(ctx.guild.id),),
  )
  ```

- [ ] **Step 6: Run tests**

  ```bash
  source venv/bin/activate && python3 -m pytest tests/ -v
  ```

  Expected: all tests pass.

- [ ] **Step 7: Commit**

  ```bash
  git add cogs/economy.py
  git commit -m "fix: update economy.py raw SQL to use _PH placeholder for Postgres compat"
  ```

---

### Task 14: Add `logger.py` and Update `main.py`

- [ ] **Step 1: Create `logger.py`**

  ```python
  import logging
  import json


  class _JSONFormatter(logging.Formatter):
      def format(self, record):
          log = {
              "level": record.levelname,
              "logger": record.name,
              "message": record.getMessage(),
          }
          if record.exc_info:
              log["exception"] = self.formatException(record.exc_info)
          return json.dumps(log)


  def get_logger(name: str) -> logging.Logger:
      logger = logging.getLogger(name)
      if not logger.handlers:
          handler = logging.StreamHandler()
          handler.setFormatter(_JSONFormatter())
          logger.addHandler(handler)
          logger.setLevel(logging.INFO)
      return logger
  ```

- [ ] **Step 2: Update `main.py` — replace `print()` with logger**

  Add import at the top of `main.py` (after existing imports):
  ```python
  from logger import get_logger

  _log = get_logger(__name__)
  ```

  Replace the `print` in `on_ready`:
  ```python
  @bot.event
  async def on_ready():
      _log.info(f"Bot ready: {bot.user}")
  ```

- [ ] **Step 3: Run tests**

  ```bash
  source venv/bin/activate && python3 -m pytest tests/ -v
  ```

  Expected: all tests pass.

- [ ] **Step 4: Commit**

  ```bash
  git add logger.py main.py
  git commit -m "feat: add structured JSON logger; replace print in main.py"
  ```

---

### Task 15: Update `requirements.txt`

- [ ] **Step 1: Add `psycopg2-binary` to `requirements.txt`**

  Open `requirements.txt` and add after the existing entries:
  ```
  psycopg2-binary==2.9.10
  ```

- [ ] **Step 2: Install it locally to verify**

  ```bash
  source venv/bin/activate && pip install psycopg2-binary==2.9.10
  ```

  Expected: `Successfully installed psycopg2-binary-2.9.10`

- [ ] **Step 3: Run tests**

  ```bash
  python3 -m pytest tests/ -v
  ```

  Expected: all tests pass.

- [ ] **Step 4: Commit**

  ```bash
  git add requirements.txt
  git commit -m "chore: add psycopg2-binary for Postgres support"
  ```

---

## Phase 5: CI/CD Pipeline

### Task 16: Set GitHub Secrets

- [ ] **Step 1: Navigate to your GitHub repo → Settings → Secrets and variables → Actions → New repository secret**

  Add these three secrets one at a time:

  | Name | Value |
  |------|-------|
  | `AWS_ACCESS_KEY_ID` | Your IAM user access key ID (from Task 1 CSV) |
  | `AWS_SECRET_ACCESS_KEY` | Your IAM user secret access key (from Task 1 CSV) |
  | `AWS_REGION` | `us-west-1` |

  Each secret: click **New repository secret**, enter the name and value, click **Add secret**.

---

### Task 17: Write `.github/workflows/deploy.yml`

- [ ] **Step 1: Create `.github/workflows/` directory structure and write `deploy.yml`**

  Replace `YOUR_ACCOUNT_ID` with your actual 12-digit AWS account ID:

  ```yaml
  name: Deploy

  on:
    push:
      branches: [main]

  jobs:
    test:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4

        - uses: actions/setup-python@v5
          with:
            python-version: "3.11"

        - name: Install dependencies
          run: pip install -r requirements.txt

        - name: Run tests
          run: python -m pytest tests/ -v

    deploy:
      needs: test
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4

        - name: Configure AWS credentials
          uses: aws-actions/configure-aws-credentials@v4
          with:
            aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
            aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
            aws-region: ${{ secrets.AWS_REGION }}

        - name: Login to Amazon ECR
          id: login-ecr
          uses: aws-actions/amazon-ecr-login@v2

        - name: Build, tag, and push image to ECR
          env:
            ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
            ECR_REPOSITORY: bettingbot
            IMAGE_TAG: ${{ github.sha }}
          run: |
            docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
            docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG

        - name: Deploy to ECS
          env:
            ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
            ECR_REPOSITORY: bettingbot
            IMAGE_TAG: ${{ github.sha }}
          run: |
            TASK_DEF=$(aws ecs describe-task-definition --task-definition bettingbot --query taskDefinition --output json)
            NEW_TASK_DEF=$(echo $TASK_DEF | jq --arg IMAGE "$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG" \
              '.containerDefinitions[0].image = $IMAGE | del(.taskDefinitionArn,.revision,.status,.requiresAttributes,.placementConstraints,.compatibilities,.registeredAt,.registeredBy)')
            NEW_ARN=$(aws ecs register-task-definition --cli-input-json "$NEW_TASK_DEF" --query taskDefinition.taskDefinitionArn --output text)
            aws ecs update-service --cluster bettingbot --service bettingbot --task-definition $NEW_ARN
            aws ecs wait services-stable --cluster bettingbot --services bettingbot
  ```

- [ ] **Step 2: Commit and push to `main`**

  ```bash
  git add .github/
  git commit -m "feat: add GitHub Actions CI/CD pipeline (test → ECR → ECS deploy)"
  git push origin main
  ```

- [ ] **Step 3: Watch the pipeline run**

  Go to your GitHub repo → **Actions** tab. You should see a workflow run triggered by your push.

  Expected flow:
  1. `test` job runs (~1 min) — all tests pass
  2. `deploy` job starts — builds Docker image, pushes to ECR, deploys to ECS (~3-5 min)
  3. Both jobs show green checkmarks

  If `deploy` fails, click into it to read the error. Common first-run issues:
  - `ResourceNotFoundException` on task definition → Terraform apply didn't complete, re-run it
  - `AccessDenied` → GitHub Secrets have wrong values, re-check them

---

## Phase 6: Data Migration

### Task 18: Write Migration Script

- [ ] **Step 1: Create `scripts/` directory and write `scripts/migrate_sqlite_to_postgres.py`**

  ```python
  """
  One-time migration: copy all data from SQLite (Pi) to RDS Postgres.
  Run from your laptop with the SQLite file copied from the Pi.

  Usage:
      SQLITE_PATH=/path/to/betting.db \
      DATABASE_URL=postgresql://bettingbot:PASSWORD@RDS_ENDPOINT/bettingbot \
      python scripts/migrate_sqlite_to_postgres.py
  """
  import os
  import sqlite3
  import psycopg2

  SQLITE_PATH = os.environ.get("SQLITE_PATH", "data/betting.db")
  DATABASE_URL = os.environ["DATABASE_URL"]

  sqlite_conn = sqlite3.connect(SQLITE_PATH)
  pg_conn = psycopg2.connect(DATABASE_URL)
  pg = pg_conn.cursor()

  print(f"Connecting to SQLite: {SQLITE_PATH}")
  print(f"Connecting to Postgres: {DATABASE_URL[:30]}...")

  # Users
  rows = sqlite_conn.execute(
      "SELECT user_id, guild_id, monies, carats, vc_minutes, last_daily FROM users"
  ).fetchall()
  for row in rows:
      pg.execute("""
          INSERT INTO users (user_id, guild_id, monies, carats, vc_minutes, last_daily)
          VALUES (%s, %s, %s, %s, %s, %s)
          ON CONFLICT (user_id, guild_id) DO NOTHING
      """, row)
  print(f"Migrated {len(rows)} users")

  # Bets
  rows = sqlite_conn.execute(
      "SELECT bet_id, guild_id, creator_id, description, status FROM bets"
  ).fetchall()
  for row in rows:
      pg.execute("""
          INSERT INTO bets (bet_id, guild_id, creator_id, description, status)
          VALUES (%s, %s, %s, %s, %s)
          ON CONFLICT (bet_id) DO NOTHING
      """, row)
  print(f"Migrated {len(rows)} bets")

  # Bet options
  rows = sqlite_conn.execute(
      "SELECT option_id, bet_id, name, total_amount FROM bet_options"
  ).fetchall()
  for row in rows:
      pg.execute("""
          INSERT INTO bet_options (option_id, bet_id, name, total_amount)
          VALUES (%s, %s, %s, %s)
          ON CONFLICT (option_id) DO NOTHING
      """, row)
  print(f"Migrated {len(rows)} bet options")

  # Wagers
  rows = sqlite_conn.execute(
      "SELECT wager_id, bet_id, option_id, user_id, amount FROM wagers"
  ).fetchall()
  for row in rows:
      pg.execute("""
          INSERT INTO wagers (wager_id, bet_id, option_id, user_id, amount)
          VALUES (%s, %s, %s, %s, %s)
          ON CONFLICT (wager_id) DO NOTHING
      """, row)
  print(f"Migrated {len(rows)} wagers")

  # Race config
  rows = sqlite_conn.execute(
      "SELECT guild_id, channel_id FROM race_config"
  ).fetchall()
  for row in rows:
      pg.execute("""
          INSERT INTO race_config (guild_id, channel_id)
          VALUES (%s, %s)
          ON CONFLICT (guild_id) DO NOTHING
      """, row)
  print(f"Migrated {len(rows)} race configs")

  # Race notifications
  rows = sqlite_conn.execute(
      "SELECT user_id, guild_id FROM race_notifications"
  ).fetchall()
  for row in rows:
      pg.execute("""
          INSERT INTO race_notifications (user_id, guild_id)
          VALUES (%s, %s)
          ON CONFLICT (user_id, guild_id) DO NOTHING
      """, row)
  print(f"Migrated {len(rows)} race notification enrollments")

  # Reset SERIAL sequences so new inserts don't conflict with migrated IDs
  pg.execute("SELECT setval('bets_bet_id_seq', COALESCE((SELECT MAX(bet_id) FROM bets), 1))")
  pg.execute("SELECT setval('bet_options_option_id_seq', COALESCE((SELECT MAX(option_id) FROM bet_options), 1))")
  pg.execute("SELECT setval('wagers_wager_id_seq', COALESCE((SELECT MAX(wager_id) FROM wagers), 1))")

  pg_conn.commit()
  print("Migration complete. All sequences reset.")

  sqlite_conn.close()
  pg_conn.close()
  ```

- [ ] **Step 2: Commit the script**

  ```bash
  git add scripts/
  git commit -m "feat: add SQLite to Postgres migration script"
  git push origin main
  ```

---

### Task 19: Run the Migration

Do this after the GitHub Actions deploy (Task 16) succeeds and the bot is running on AWS.

- [ ] **Step 1: Temporarily allow public access to RDS for migration**

  The RDS instance is in a private subnet — your laptop can't reach it directly. Temporarily open port 5432 from your IP:

  In the AWS Console:
  - Search **EC2** → **Security Groups** → find `bettingbot-rds-sg`
  - **Inbound rules** → **Edit inbound rules** → **Add rule**
  - Type: `PostgreSQL`, Source: `My IP`
  - Save

- [ ] **Step 2: Copy `betting.db` from your Pi to your laptop**

  Run this on your laptop (replace `PI_IP` with your Pi's IP address):
  ```bash
  scp pi@PI_IP:/path/to/bettingbot/data/betting.db ./betting_pi.db
  ```

- [ ] **Step 3: Run the migration script**

  Replace `PASSWORD` with your `db_password` from `terraform.tfvars` and `RDS_ENDPOINT` with the endpoint from Terraform outputs (without the `:5432` port — psycopg2 handles that in the URL):

  ```bash
  source venv/bin/activate
  SQLITE_PATH=./betting_pi.db DATABASE_URL="postgresql://bettingbot:PASSWORD@RDS_ENDPOINT/bettingbot" python scripts/migrate_sqlite_to_postgres.py
  ```

  Expected output:
  ```
  Connecting to SQLite: ./betting_pi.db
  Connecting to Postgres: postgresql://bettingbot:...
  Migrated X users
  Migrated X bets
  Migrated X bet options
  Migrated X wagers
  Migrated X race configs
  Migrated X race notification enrollments
  Migration complete. All sequences reset.
  ```

- [ ] **Step 4: Verify data in Postgres**

  ```bash
  psql "postgresql://bettingbot:PASSWORD@RDS_ENDPOINT/bettingbot" -c "SELECT COUNT(*) FROM users;"
  ```

  Count should match what you saw in the migration output.

- [ ] **Step 5: Remove the temporary inbound rule from `bettingbot-rds-sg`**

  Back in the AWS Console → EC2 → Security Groups → `bettingbot-rds-sg` → Edit inbound rules → delete the `My IP` rule you added → Save.

---

## Phase 7: Verify & Cutover

### Task 20: Verify Bot is Live and Shut Down Pi Bot

- [ ] **Step 1: Test the bot in Discord**

  In your Discord server, run:
  ```
  !balance
  !daily
  !leaderboard
  ```

  All commands should respond correctly. Check that balances match what was on the Pi.

- [ ] **Step 2: Check CloudWatch logs**

  AWS Console → CloudWatch → Log groups → `/ecs/bettingbot` → click the latest log stream.

  You should see JSON log lines like:
  ```json
  {"level": "INFO", "logger": "__main__", "message": "Bot ready: BotName#1234"}
  ```

- [ ] **Step 3: Confirm you received the SNS email subscription confirmation**

  If you haven't already, check your email and confirm the SNS subscription — otherwise crash alerts won't arrive.

- [ ] **Step 4: Stop the Pi bot**

  SSH into your Pi and stop the bot process:
  ```bash
  # Find and kill the bot process
  pkill -f "python main.py"
  # Or if running as a systemd service:
  sudo systemctl stop bettingbot
  ```

  The AWS bot is now the only running instance.

- [ ] **Step 5: Final end-to-end test**

  Run `!race` and place a bet to confirm the full flow works end-to-end with the Postgres database.

---

## Done

Your bettingbot is now running in production on AWS with:
- **ECS Fargate** — serverless container, auto-restarts on crash
- **RDS Postgres** — managed database with 7-day backups
- **GitHub Actions** — deploys automatically on every push to `main`
- **Terraform** — entire infrastructure reproducible from code
- **Secrets Manager** — no secrets in code or `.env`
- **CloudWatch + SNS** — crash alerts to your email

Resume bullet points:
```
• Containerized Python Discord bot with Docker; deployed to AWS ECS Fargate
• Built CI/CD pipeline (GitHub Actions: pytest → ECR → ECS) with zero-downtime deploys
• Provisioned all infrastructure as code with Terraform (VPC, ECS, RDS, IAM, Secrets Manager)
• Migrated production SQLite database to RDS Postgres with zero data loss
• Instrumented with structured JSON logging and crash alerting via CloudWatch + SNS
```
