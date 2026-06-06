resource "aws_sqs_queue" "eventbridge_dlq" {
  name = "eventbridge-dlq"
}

resource "aws_cloudwatch_event_rule" "backfill_rules" {
  for_each = var.fifo_queues

  name        = "backfill-${each.key}"
  description = "Route backfill events for ${each.key} to its FIFO queue"

  event_pattern = jsonencode({
    "detail-type" : ["backfill.request"],
    "detail" : {
      "target" : [each.key]
    }
  })

}

resource "aws_cloudwatch_event_target" "backfill_targets" {
  for_each = var.fifo_queues

  rule           = aws_cloudwatch_event_rule.backfill_rules[each.key].name
  target_id      = "send-to-${each.key}"
  arn            = aws_sqs_queue.fifo[each.key].arn
  event_bus_name = "default"

  dead_letter_config {
    arn = aws_sqs_queue.eventbridge_dlq.arn
  }

  # This is the only valid argument in this block for SQS FIFO
  sqs_target {
    message_group_id = "$.detail.message_group_id"
  }

  input_transformer {
    input_paths = {
      symbol    = "$.detail.symbol"
      timeframe = "$.detail.timeframe"
      start_ts  = "$.detail.start_ts"
      end_ts    = "$.detail.end_ts"
    }

    input_template = <<EOF
{
  "symbol": "<symbol>",
  "timeframe": "<timeframe>",
  "start_ts": "<start_ts>",
  "end_ts": "<end_ts>"
}
EOF
  }
}

resource "aws_sqs_queue_policy" "fifo_policy" {
  for_each = var.fifo_queues

  queue_url = aws_sqs_queue.fifo[each.key].id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "events.amazonaws.com" },
      Action    = "sqs:SendMessage",
      Resource  = aws_sqs_queue.fifo[each.key].arn,
      Condition = {
        ArnEquals = {
          "aws:SourceArn" = aws_cloudwatch_event_rule.backfill_rules[each.key].arn
        }
      }
    }]
  })
}


resource "aws_sqs_queue_policy" "dlq_policy" {
  queue_url = aws_sqs_queue.eventbridge_dlq.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect    = "Allow",
      Principal = { Service = "events.amazonaws.com" },
      Action    = "sqs:SendMessage",
      Resource  = aws_sqs_queue.eventbridge_dlq.arn
    }]
  })
}

