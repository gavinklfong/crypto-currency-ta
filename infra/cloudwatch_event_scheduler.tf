# 1. Flatten the nested map/list into a single flat map
locals {
  flat_schedules = flatten([
    for lambda_key, lambda_config in var.lambdas : [
      for schedule in coalesce(lambda_config.schedules, []) : {
        lambda_key   = lambda_key
        lambda_name  = lambda_config.function_name
        rule_name    = schedule.name
        schedule_exp = schedule.schedule
        event_input  = schedule.event_input

        # Create a unique key for the for_each loop
        unique_key = "${lambda_key}-${schedule.name}"
      }
    ]
  ])

  schedule_map = {
    for item in local.flat_schedules : item.unique_key => item
  }
}

# 2. Create the CloudWatch Event Rules (EventBridge)
resource "aws_cloudwatch_event_rule" "schedule" {
  for_each = local.schedule_map

  name                = each.value.rule_name
  description         = "Triggers Lambda ${each.value.lambda_name}"
  schedule_expression = each.value.schedule_exp
}

# 3. Create the CloudWatch Event Targets pointing to your Lambda
resource "aws_cloudwatch_event_target" "lambda_target" {
  for_each = local.schedule_map

  rule      = aws_cloudwatch_event_rule.schedule[each.key].name
  target_id = "${each.value.lambda_name}-Target"

  # References your specific lambda resource name
  arn = aws_lambda_function.lambda[each.value.lambda_key].arn

  # Inject the event_input if it exists
  input = each.value.event_input != null ? jsonencode(each.value.event_input) : null
}

# 4. Grant EventBridge permission to invoke the Lambda functions
resource "aws_lambda_permission" "allow_cloudwatch" {
  for_each = local.schedule_map

  statement_id = "AllowExecutionFromCloudWatch-${each.value.rule_name}"
  action       = "lambda:InvokeFunction"

  # References your specific lambda resource name
  function_name = aws_lambda_function.lambda[each.value.lambda_key].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.schedule[each.key].arn
}
