########################################
# IAM Role (shared by all Lambdas)
########################################

resource "aws_iam_role" "lambda_exec" {
  name = var.lambda_exec_role_name

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}


########################################
# Lambda Functions
########################################

resource "aws_lambda_function" "lambda" {
  for_each = var.lambdas

  function_name = each.value.function_name
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"

  filename         = each.value.zip_path
  source_code_hash = filebase64sha256(each.value.zip_path)

  role = aws_iam_role.lambda_exec.arn
}

########################################
# Lambda Permissions (auto-generated)
########################################

resource "aws_lambda_permission" "allow_apigw" {
  for_each = var.lambdas

  statement_id  = "AllowAPIGatewayInvoke-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda[each.key].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}
