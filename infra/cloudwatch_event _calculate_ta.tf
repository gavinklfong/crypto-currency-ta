########################################################################
# EventBridge Rule for Market Data Updated Events
########################################################################

########################################################################
# EventBridge Rule for Market Data Updated Events
########################################################################

resource "aws_cloudwatch_event_rule" "market_data_updated" {
  name        = "market-data-updated-rule"
  description = "Route market-data-updated events from fetch-market-data to TA calculation lambda"

  event_pattern = jsonencode({
    source      = ["market-data-fetcher"]
    detail-type = ["market-data-updated"]
  })
}

########################################################################
# Direct EventBridge → Lambda Target
########################################################################

resource "aws_cloudwatch_event_target" "market_data_to_lambda" {
  rule      = aws_cloudwatch_event_rule.market_data_updated.name
  target_id = "invoke-ta-lambda"
  arn       = aws_lambda_function.lambda["calculate_ta"].arn
}

########################################################################
# Allow EventBridge to Invoke the Lambda
########################################################################

resource "aws_lambda_permission" "allow_eventbridge_invoke" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda["calculate_ta"].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.market_data_updated.arn
}
