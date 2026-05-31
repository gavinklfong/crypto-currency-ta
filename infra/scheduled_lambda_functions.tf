########################################
# Lambda with schedules Functions
########################################

resource "aws_lambda_function" "scheduled_lambda" {
  for_each = var.scheduled_lambdas

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
