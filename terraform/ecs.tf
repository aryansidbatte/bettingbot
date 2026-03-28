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
