###############################################
# 1. FIFO SQS QUEUE (3‑second delay)
# ---------------------------------------------
# This queue receives EventBridge events and 
# triggers the rerun-fetch-market-data Lambda.
# FIFO ensures strict ordering and deduplication.
###############################################
resource "aws_sqs_queue" "rerun_fetch_fifo" {
  name                        = "rerun-fetch-market-data.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
  delay_seconds               = 3

  visibility_timeout_seconds = 60
}

###############################################
# 9. REDRIVE POLICY FOR FIFO QUEUE
# ---------------------------------------------
# If Lambda fails to process a message 5 times,
# SQS moves it to the DLQ automatically.
###############################################
resource "aws_sqs_queue_redrive_policy" "rerun_fetch_redrive" {
  queue_url = aws_sqs_queue.rerun_fetch_fifo.id

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.rerun_fetch_dlq.arn
    maxReceiveCount     = 5
  })
}

###############################################
# 8. DEAD-LETTER QUEUE (DLQ)
# ---------------------------------------------
# Stores messages that fail Lambda processing
# after maxReceiveCount attempts.
###############################################
resource "aws_sqs_queue" "rerun_fetch_dlq" {
  name                        = "rerun-fetch-market-data-dlq.fifo"
  fifo_queue                  = true
  content_based_deduplication = true
}


###############################################
# 2. EVENTBRIDGE RULE
# ---------------------------------------------
# Matches events emitted by the Lambda:
#   Source      = "fetch.market.data"
#   DetailType  = "fetch-more"
#
# When matched, EventBridge forwards the event 
# to the FIFO SQS queue defined above.
###############################################
resource "aws_cloudwatch_event_rule" "rerun_fetch_rule" {
  name        = "rerun-fetch-market-data-rule"
  description = "Route fetch-more events to FIFO SQS"

  event_pattern = jsonencode({
    "source" : ["rerun-fetch-market-data"],
    "detail-type" : ["fetch-more-market-data"]
  })
}

###############################################
# 3. EVENTBRIDGE TARGET → SQS
# ---------------------------------------------
# Connects the EventBridge rule to the FIFO SQS queue.
# Every matching event is delivered to the queue.
###############################################
resource "aws_cloudwatch_event_target" "rerun_fetch_target" {
  rule      = aws_cloudwatch_event_rule.rerun_fetch_rule.name
  target_id = "send-to-rerun-fetch-fifo"
  arn       = aws_sqs_queue.rerun_fetch_fifo.arn

  sqs_target {
    message_group_id = "rerun-fetch-group"
  }
}

###############################################
# 4. SQS QUEUE POLICY
# ---------------------------------------------
# Allows EventBridge to send messages to the FIFO queue.
# Without this, EventBridge → SQS delivery will fail.
###############################################
resource "aws_sqs_queue_policy" "rerun_fetch_fifo_policy" {
  queue_url = aws_sqs_queue.rerun_fetch_fifo.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "events.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.rerun_fetch_fifo.arn
    }]
  })
}


###############################################
# 5. LAMBDA IAM PERMISSION TO EMIT EVENTS
# ---------------------------------------------
# Allows the rerun-fetch-market-data Lambda to call 
# EventBridge PutEvents(), enabling recursive scheduling.
###############################################
resource "aws_iam_role_policy" "lambda_put_events" {
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["events:PutEvents"]
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy" "lambda_sqs_permissions" {
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:GetQueueAttributes"
      ]
      Resource = aws_sqs_queue.rerun_fetch_fifo.arn
    }]
  })
}


###############################################
# 6. SQS → LAMBDA EVENT SOURCE MAPPING
# ---------------------------------------------
# Connects the FIFO SQS queue to the 
# rerun-fetch-market-data Lambda.
#
# Every message in the queue triggers the Lambda.
# batch_size = 1 ensures strict FIFO processing.
###############################################
resource "aws_lambda_event_source_mapping" "rerun_fetch_sqs_trigger" {
  event_source_arn = aws_sqs_queue.rerun_fetch_fifo.arn
  function_name    = aws_lambda_function.lambda["rerun-fetch-market-data"].arn

  batch_size                         = 1
  maximum_batching_window_in_seconds = 0
}
