locals {
  # 1. Generate every combination of Lambda x Symbol x Timeframe
  raw_targets = flatten([
    for lambda_key, lambda_config in var.lambdas : [
      for symbol in var.symbols : [
        for tf in lambda_config.timeframes : {
          target_key   = "${lambda_key}-${symbol}-${tf}"
          rule_name    = "${symbol}-${tf}"
          schedule_exp = var.timeframe_schedules[tf]
          lambda_key   = lambda_key

          # Dynamically build the event JSON
          event_input = {
            detail = merge(
              { symbol = symbol },
              { timeframe = tf }
            )
          }
        }
      ]
    ]
  ])

  # 2. Map targets for the aws_cloudwatch_event_target resource
  targets_map = {
    for target in local.raw_targets : target.target_key => target
  }

  # 3. Deduplicate Rules so multiple Lambdas can share the same CloudWatch schedule (e.g., XXBTZUSD-1m)
  unique_rules_map = {
    for target in local.raw_targets : target.rule_name => target.schedule_exp...
  }

  rules_to_create = {
    for rule_name, exps in local.unique_rules_map : rule_name => exps[0]
  }
}

# ---------------------------------------------------------
# Resources
# ---------------------------------------------------------

# Creates deduplicated CloudWatch Event Rules (e.g., just one "XXBTZUSD-1m" rule total)
resource "aws_cloudwatch_event_rule" "schedule" {
  for_each = local.rules_to_create

  name                = each.key
  description         = "Schedule rule for ${each.key}"
  schedule_expression = each.value
}

# Connects specific Lambdas to specific Rules based on their subscriptions
resource "aws_cloudwatch_event_target" "lambda_target" {
  for_each = local.targets_map

  rule      = aws_cloudwatch_event_rule.schedule[each.value.rule_name].name
  target_id = each.key
  arn       = aws_lambda_function.lambda[each.value.lambda_key].arn

  input = jsonencode(each.value.event_input)
}

# Grants EventBridge permission to invoke the targets
resource "aws_lambda_permission" "allow_cloudwatch" {
  for_each = local.targets_map

  statement_id  = "AllowEventBridge-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda[each.value.lambda_key].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.schedule[each.value.rule_name].arn
}
