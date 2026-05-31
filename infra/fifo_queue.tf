locals {
  fifo_queues = var.fifo_queues
  lambdas     = var.scheduled_lambdas
}

# -----------------------------
# 1. Create FIFO queues + DLQs
# -----------------------------
resource "aws_sqs_queue" "fifo" {
  for_each = local.fifo_queues

  name                        = each.value
  fifo_queue                  = true
  content_based_deduplication = false

  # Dynamically set based on lambda timeout
  visibility_timeout_seconds = (
    lookup(local.lambdas[each.key], "timeout", 30) * 6
  )

  receive_wait_time_seconds = 10

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq[each.key].arn
    maxReceiveCount     = 5
  })
}

resource "aws_sqs_queue" "dlq" {
  for_each = local.fifo_queues

  name       = "${replace(each.value, ".fifo", "")}-dlq.fifo"
  fifo_queue = true
}



# -----------------------------
# 2. Event source mapping
# -----------------------------
resource "aws_lambda_event_source_mapping" "fifo_trigger" {
  for_each = local.fifo_queues

  event_source_arn = aws_sqs_queue.fifo[each.key].arn
  function_name    = aws_lambda_function.scheduled_lambda[each.key].arn
  batch_size       = 1
  enabled          = true
}

# -----------------------------
# 4. IAM permissions
# -----------------------------
resource "aws_iam_role_policy" "lambda_sqs_policy" {
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ]
        Resource = [
          for q in aws_sqs_queue.fifo : q.arn
        ]
      }
    ]
  })
}
