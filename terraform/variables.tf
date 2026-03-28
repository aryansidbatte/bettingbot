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
