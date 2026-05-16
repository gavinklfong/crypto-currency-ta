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

resource "aws_sqs_queue" "ta_delay_queue" {
  name                       = "ta-delay-queue"
  delay_seconds              = 5 # delay execution by 5 seconds
  visibility_timeout_seconds = 60
}

resource "aws_sqs_queue_policy" "ta_delay_queue_policy" {
  queue_url = aws_sqs_queue.ta_delay_queue.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect    = "Allow",
        Principal = { Service = "events.amazonaws.com" },
        Action    = "sqs:SendMessage",
        Resource  = aws_sqs_queue.ta_delay_queue.arn,
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.market_data_updated.arn
          }
        }
      }
    ]
  })
}

resource "aws_cloudwatch_event_target" "market_data_to_sqs" {
  rule      = aws_cloudwatch_event_rule.market_data_updated.name
  target_id = "send-to-sqs"
  arn       = aws_sqs_queue.ta_delay_queue.arn

  dead_letter_config {
    arn = aws_sqs_queue.ta_dlq.arn
  }
}

resource "aws_lambda_event_source_mapping" "ta_sqs_trigger" {
  event_source_arn = aws_sqs_queue.ta_delay_queue.arn
  function_name    = aws_lambda_function.lambda["calculate_ta"].arn
  batch_size       = 1
  enabled          = true
}

