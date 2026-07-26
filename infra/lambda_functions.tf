locals {
  lambda_queue_map = {
    for key, _ in var.fifo_queues :
    key => aws_sqs_queue.fifo[key].url
  }

  special_lambda_env = {
    for key, val in var.lambdas :
    key => {
      LAUNCH_TEMPLATE_ID          = aws_launch_template.ec2_worker_lt.id
      JOB_SCRIPTS_BUCKET_NAME      = aws_s3_bucket.job_scripts.id
    }
    if val.is_launcher
  }

  common_lambda_env = {
    SNS_TOPIC_ARN = aws_sns_topic.slack_notifications.arn
    JOB_TRACKER_TABLE_NAME = aws_dynamodb_table.job_tracker.name
  }

  # Map of special lambdas to their custom IAM roles
  lambda_roles = {
    "ec2-reaper" = aws_iam_role.ec2_reaper_role.arn
  }
}

resource "aws_lambda_function" "lambda" {
  for_each = var.lambdas

  function_name = each.value.function_name
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  timeout       = each.value.timeout

  filename         = each.value.zip_path
  source_code_hash = filebase64sha256(each.value.zip_path)

  role = lookup(local.lambda_roles, each.key, each.value.role_arn != null ? each.value.role_arn : aws_iam_role.lambda_exec.arn)

  layers = [
    for layer_name in each.value.layers :
    aws_lambda_layer_version.layers[layer_name].arn
  ]

  environment {
    variables = merge(
      local.common_lambda_env,
      each.value.environment,
      lookup(var.lambda_env, each.key, {}),
      lookup(local.special_lambda_env, each.key, {})
    )
  }
}
