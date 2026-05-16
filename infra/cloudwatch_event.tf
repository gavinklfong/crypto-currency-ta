
########################################################################
# CloudWatch Event rules to schedule Lambda functions 
# based on the 'schedule' attribute in the lambdas variable
########################################################################
locals {
  scheduled_lambdas = {
    for k, v in var.lambdas : k => v
    if try(v.schedule, null) != null
  }
}

# CloudWatch Event Rules for scheduled Lambdas
resource "aws_cloudwatch_event_rule" "lambda_schedule" {
  for_each = local.scheduled_lambdas

  name                = "schedule-${each.key}"
  schedule_expression = each.value.schedule
}

# CloudWatch Event Targets to trigger Lambdas
resource "aws_cloudwatch_event_target" "lambda_schedule_target" {
  for_each = local.scheduled_lambdas

  rule      = aws_cloudwatch_event_rule.lambda_schedule[each.key].name
  target_id = "lambda-${each.key}"
  arn       = aws_lambda_function.lambda[each.key].arn
}

# Lambda Permissions for CloudWatch Events
resource "aws_lambda_permission" "allow_eventbridge" {
  for_each = local.scheduled_lambdas

  statement_id  = "AllowExecutionFromEventBridge-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda[each.key].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.lambda_schedule[each.key].arn
}

########################################################################
# EventBridge Rule for Market Data Updated Events
########################################################################

# EventBridge rule to listen for market-data-updated events from fetch-market-data
resource "aws_cloudwatch_event_rule" "market_data_updated" {
  name        = "market-data-updated-rule"
  description = "Route market-data-updated events from fetch-market-data to relevant targets"

  event_pattern = jsonencode({
    source      = ["market-data-fetcher"]
    detail-type = ["market-data-updated"]
  })
}

# DLQ for TA calculation failures
resource "aws_sqs_queue" "ta_dlq" {
  name = "ta-calculation-dlq"
}

# Target the calculate-ta Lambda for market-data-updated events
resource "aws_cloudwatch_event_target" "calculate_ta_target" {
  rule      = aws_cloudwatch_event_rule.market_data_updated.name
  target_id = "calculate-ta-lambda"
  arn       = aws_lambda_function.lambda["calculate_ta"].arn

  retry_policy {
    maximum_retry_attempts       = 10  # Retry up to 10 times
    maximum_event_age_in_seconds = 900 # Give up and send to DLQ after 15 minutes
  }

  dead_letter_config {
    arn = aws_sqs_queue.ta_dlq.arn
  }
}


# Lambda permission to allow EventBridge to invoke calculate-ta
resource "aws_lambda_permission" "allow_eventbridge_market_data_updated" {
  statement_id  = "AllowExecutionFromEventBridgeMarketDataUpdated"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda["calculate_ta"].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.market_data_updated.arn
}
