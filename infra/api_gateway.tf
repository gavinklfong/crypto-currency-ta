# This file defines the API Gateway resources and their integration with Lambda functions.
# It also sets up the necessary permissions for Lambda to be invoked by API Gateway.
locals {
  lambdas_with_routes = {
    for k, v in var.scheduled_lambdas :
    k => v
    if try(v.route_key, null) != null
  }
}

########################################
# API Gateway HTTP API
########################################

resource "aws_apigatewayv2_api" "http_api" {
  name          = var.api_gateway_name
  protocol_type = "HTTP"
}

########################################
# Integrations (only for lambdas with route_key)
########################################

resource "aws_apigatewayv2_integration" "integration" {
  for_each = local.lambdas_with_routes

  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.scheduled_lambda[each.key].invoke_arn
  payload_format_version = "2.0"
}

########################################
# Routes (only for lambdas with route_key)
########################################

resource "aws_apigatewayv2_route" "route" {
  for_each = merge(
    {
      for k, v in local.lambdas_with_routes :
      k => {
        route_key = v.route_key
        lambda    = k
      }
    },
    var.extra_routes
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
# Lambda Permissions (only for lambdas with route_key)
########################################

resource "aws_lambda_permission" "allow_apigw" {
  for_each = local.lambdas_with_routes

  statement_id  = "AllowAPIGatewayInvoke-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.scheduled_lambda[each.key].function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

########################################
# API Gateway Outputs
########################################

output "api_invoke_url" {
  description = "HTTP API invoke URL"
  value       = aws_apigatewayv2_stage.default_stage.invoke_url
}
