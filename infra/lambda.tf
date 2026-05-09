provider "aws" {
  region = "us-east-2"
}

########################################
# IAM Role (shared by all Lambdas)
########################################

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

########################################
# Define all Lambda functions here
########################################

locals {
  lambdas = {
    hello1 = {
      function_name = "hello-world-lambda-1"
      zip_path      = "${path.module}/../.package/deployment-function-1.zip"
      route_key     = "GET /hello-1"
    }
    hello2 = {
      function_name = "hello-world-lambda-2"
      zip_path      = "${path.module}/../.package/deployment-function-2.zip"
      route_key     = "GET /hello-2"
    }
  }

  # Additional routes that reuse existing Lambdas
  extra_routes = {
    root = {
      route_key = "GET /"
      lambda    = "hello1" # reference existing lambda
    }
  }
}


########################################
# Lambda Functions
########################################

resource "aws_lambda_function" "lambda" {
  for_each = local.lambdas

  function_name = each.value.function_name
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"

  filename         = each.value.zip_path
  source_code_hash = filebase64sha256(each.value.zip_path)

  role = aws_iam_role.lambda_exec.arn

  environment {
    variables = {
      TIMESTREAM_DATABASE_NAME = local.timestream_database_name
      TIMESTREAM_TABLE_NAME    = local.timestream_table_name
    }
  }
}

########################################
# API Gateway HTTP API
########################################

resource "aws_apigatewayv2_api" "http_api" {
  name          = "hello-world-http-api"
  protocol_type = "HTTP"
}

########################################
# Integrations
########################################

resource "aws_apigatewayv2_integration" "integration" {
  for_each = local.lambdas

  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.lambda[each.key].invoke_arn
  payload_format_version = "2.0"
}

########################################
# Routes
########################################

resource "aws_apigatewayv2_route" "route" {
  for_each = merge(
    { for k, v in local.lambdas : k => {
      route_key = v.route_key
      lambda    = k
    } },
    local.extra_routes
  )

  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = each.value.route_key
  target    = "integrations/${aws_apigatewayv2_integration.integration[each.value.lambda].id}"
}


########################################
# Stage
########################################

resource "aws_apigatewayv2_stage" "default_stage" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "$default"
  auto_deploy = true
}

########################################
# Lambda Permissions (auto-generated)
########################################

resource "aws_lambda_permission" "allow_apigw" {
  for_each = local.lambdas

  statement_id  = "AllowAPIGatewayInvoke-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda[each.key].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

########################################
# Output
########################################

output "api_invoke_url" {
  value = aws_apigatewayv2_stage.default_stage.invoke_url
}
