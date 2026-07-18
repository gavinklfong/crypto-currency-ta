locals {
  lambda_queue_map = {
    for key, _ in var.fifo_queues :
    key => aws_sqs_queue.fifo[key].url
  }

  special_lambda_env = {
    for key, val in var.lambdas :
    key => {
      LAUNCH_TEMPLATE_ID          = aws_launch_template.ec2_worker_lt.id
      TA_JOB_SCRIPTS_BUCKET_NAME = aws_s3_bucket.ta_job_scripts.id
    }
    if val.is_launcher
  }

  common_lambda_env = {
    SNS_TOPIC_ARN = aws_sns_topic.slack_notifications.arn
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

  role = aws_iam_role.lambda_exec.arn

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
