
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

  # Pass event data to Lambda (e.g., cryptocurrency symbols)
  input = try(each.value.event_input, null) != null ? each.value.event_input : null
}

# Lambda Permissions for CloudWatch Events
resource "aws_lambda_permission" "lambda_schedule_allow_eventbridge" {
  for_each = local.scheduled_lambdas

  statement_id  = "AllowExecutionFromEventBridge-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda[each.key].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.lambda_schedule[each.key].arn
}
