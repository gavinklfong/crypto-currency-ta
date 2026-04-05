provider "aws" {
  region = "us-east-2"
}

# Lambda function and execution role
resource "aws_iam_role" "lambda_exec" {
  name = "hello-world-lambda-exec"

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

resource "aws_lambda_function" "hello_world_1" {
  function_name = "hello-world-lambda-1"
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"

  filename         = "${path.module}/../deployment-function-1.zip"
  source_code_hash = filebase64sha256("${path.module}/../deployment-function-1.zip")

  role = aws_iam_role.lambda_exec.arn
}

resource "aws_lambda_function" "hello_world_2" {
  function_name = "hello-world-lambda-2"
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"

  filename         = "${path.module}/../deployment-function-2.zip"
  source_code_hash = filebase64sha256("${path.module}/../deployment-function-2.zip")

  role = aws_iam_role.lambda_exec.arn
}


########################################
# API Gateway HTTP API (v2)
########################################

resource "aws_apigatewayv2_api" "http_api" {
  name          = "hello-world-http-api"
  protocol_type = "HTTP"
}

# hello 1
resource "aws_apigatewayv2_integration" "lambda_1_integration" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.hello_world_1.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "hello_1_route" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "GET /hello-1"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_1_integration.id}"

  depends_on = [
    aws_apigatewayv2_integration.lambda_1_integration
  ]
}

# hello 2
resource "aws_apigatewayv2_integration" "lambda_2_integration" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.hello_world_2.invoke_arn
  payload_format_version = "2.0"
}
resource "aws_apigatewayv2_route" "hello_2_route" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "GET /hello-2"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_2_integration.id}"

  depends_on = [
    aws_apigatewayv2_integration.lambda_2_integration
  ]

}


resource "aws_apigatewayv2_route" "default_route" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "GET /"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_1_integration.id}"

  depends_on = [
    aws_apigatewayv2_integration.lambda_1_integration
  ]
}

resource "aws_apigatewayv2_stage" "default_stage" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true
}

########################################
# Lambda permission for API Gateway
########################################

resource "aws_lambda_permission" "allow_apigw_1" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.hello_world_1.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "allow_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.hello_world_2.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

########################################
# Output the public URL
########################################

output "api_invoke_url" {
  value = aws_apigatewayv2_stage.default_stage.invoke_url
}
