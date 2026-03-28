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
    source        = ["aws.ecs"]
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
