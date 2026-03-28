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
