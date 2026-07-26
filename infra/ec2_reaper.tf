# EC2 Reaper Lambda Configuration

resource "aws_lambda_function" "ec2_reaper" {
  function_name = "ec2-reaper"
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  timeout       = 60

  filename         = "../build/package/lambdas/ec2-reaper.zip"
  source_code_hash = filebase64sha256("../build/package/lambdas/ec2-reaper.zip")

  role = aws_iam_role.ec2_reaper_role.arn

  environment {
    variables = {
      JOB_TRACKER_TABLE_NAME    = aws_dynamodb_table.job_tracker.name
      MAX_INACTIVITY_MINUTES    = "30"
      MAX_LIFETIME_HOURS        = "8"
    }
  }
}

# IAM Role for EC2 Reaper
resource "aws_iam_role" "ec2_reaper_role" {
  name = "ec2-reaper-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

# IAM Policy for EC2 Reaper
resource "aws_iam_role_policy" "ec2_reaper_policy" {
  name = "ec2-reaper-policy"
  role = aws_iam_role.ec2_reaper_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Logging
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        # EC2 Management
        Effect = "Allow"
        Action = [
          "ec2:DescribeInstances",
          "ec2:TerminateInstances"
        ]
        Resource = "*"
      },
      {
        # Job Tracker Access
        Effect = "Allow"
        Action = [
          "dynamodb:Scan",
          "dynamodb:UpdateItem"
        ]
        Resource = [
          aws_dynamodb_table.job_tracker.arn,
          "${aws_dynamodb_table.job_tracker.arn}/*"
        ]
      }
    ]
  })
}

# EventBridge Schedule for the Reaper
resource "aws_cloudwatch_event_rule" "ec2_reaper_schedule" {
  name                = "ec2-reaper-schedule"
  description         = "Triggers the EC2 Reaper Lambda every 30 minutes"
  schedule_expression = "rate(30 minutes)"
}

resource "aws_cloudwatch_event_target" "ec2_reaper_target" {
  rule      = aws_cloudwatch_event_rule.ec2_reaper_schedule.name
  target_id = "ec2_reaper_lambda"
  arn       = aws_lambda_function.ec2_reaper.arn
}

# Permission for EventBridge to invoke the Reaper
resource "aws_lambda_permission" "allow_eventbridge_to_call_reaper" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ec2_reaper.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ec2_reaper_schedule.arn
}
