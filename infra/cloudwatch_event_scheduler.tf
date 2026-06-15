locals {
  # 1. Build schedule maps for each Lambda by merging global schedules with function-specific overrides
  function_schedule_maps = {
    for lambda_key, lambda_config in var.lambdas : lambda_key => merge(
      var.timeframe_schedules,
      lambda_config.schedule_overrides
    )
  }

  # 2. Generate every combination of Lambda x Symbol x Timeframe
  #    Each target gets the schedule expression specific to that Lambda
  raw_targets = flatten([
    for lambda_key, lambda_config in var.lambdas : [
      for symbol in var.symbols : [
        for tf in lambda_config.timeframes : {
          target_key   = "${lambda_key}-${symbol}-${tf}"
          lambda_key   = lambda_key
          symbol       = symbol
          timeframe    = tf
          schedule_exp = local.function_schedule_maps[lambda_key][tf]

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

  # 3. Map targets for the aws_cloudwatch_event_target resource
  targets_map = {
    for target in local.raw_targets : target.target_key => target
  }

  # 4. Check for schedule conflicts:
  #    Group all targets by {symbol}-{timeframe} and collect unique schedule expressions
  symbol_tf_schedules = {
    for target in local.raw_targets :
    "${target.symbol}-${target.timeframe}" => target.schedule_exp...
  }

  # Find which {symbol}-{timeframe} pairs have conflicting schedules
  conflicting_pairs = {
    for key, exps in local.symbol_tf_schedules :
    key => distinct(exps)
    if length(distinct(exps)) > 1
  }

  # 5. Create rule names:
  #    - For non-conflicting {symbol}-{timeframe}: use simple name (backward compatible)
  #    - For conflicting pairs: add hash suffix to differentiate schedules
  rules_map = {
    for target in local.raw_targets :
    (
      contains(keys(local.conflicting_pairs), "${target.symbol}-${target.timeframe}") ?
      "${target.symbol}-${target.timeframe}-${substr(md5(target.schedule_exp), 0, 8)}" :
      "${target.symbol}-${target.timeframe}"
      ) => {
      symbol       = target.symbol
      timeframe    = target.timeframe
      schedule_exp = target.schedule_exp
      display_name = "${target.symbol}-${target.timeframe}"
    }...
  }

  rules_to_create = {
    for rule_key, rule_data in local.rules_map : rule_key => rule_data[0]
  }

  # 6. Build a lookup table to map targets to their actual rule names
  target_to_rule_map = {
    for target in local.raw_targets :
    target.target_key => (
      contains(keys(local.conflicting_pairs), "${target.symbol}-${target.timeframe}") ?
      "${target.symbol}-${target.timeframe}-${substr(md5(target.schedule_exp), 0, 8)}" :
      "${target.symbol}-${target.timeframe}"
    )
  }
}

# ---------------------------------------------------------
# Resources
# ---------------------------------------------------------

# Creates deduplicated CloudWatch Event Rules for each unique {symbol}-{timeframe}-{schedule} combination
# Different Lambdas with different schedules get separate rules; Lambdas with same schedule share rules
resource "aws_cloudwatch_event_rule" "schedule" {
  for_each = local.rules_to_create

  name                = each.key
  description         = "Schedule rule for ${each.value.display_name} (${each.value.schedule_exp})"
  schedule_expression = each.value.schedule_exp
}

# Connects specific Lambdas to specific Rules based on their subscriptions and schedules
resource "aws_cloudwatch_event_target" "lambda_target" {
  for_each = local.targets_map

  # Use the target_to_rule_map to find the correct rule for this target
  rule      = aws_cloudwatch_event_rule.schedule[local.target_to_rule_map[each.key]].name
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
  source_arn    = aws_cloudwatch_event_rule.schedule[local.target_to_rule_map[each.key]].arn
}
