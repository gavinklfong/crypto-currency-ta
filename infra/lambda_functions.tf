locals {
  lambda_queue_map = {
    for key, _ in var.fifo_queues :
    key => aws_sqs_queue.fifo[key].url
  }
}

resource "aws_lambda_function" "lambda" {
  for_each = var.lambdas

  function_name = each.value.function_name
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"
  timeout       = each.value.timeout

  filename         = each.value.zip_path
  source_code_hash = filebase64sha256(each.value.zip_path)

  role = aws_iam_role.lambda_exec.arn

  layers = [
    for layer_name in each.value.layers :
    aws_lambda_layer_version.layers[layer_name].arn
  ]
}
