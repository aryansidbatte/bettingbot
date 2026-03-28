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
