########################################
# API Gateway HTTP API
########################################

resource "aws_apigatewayv2_api" "http_api" {
  name          = var.api_gateway_name
  protocol_type = "HTTP"
}

########################################
# Integrations
########################################

resource "aws_apigatewayv2_integration" "integration" {
  for_each = var.lambdas

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
    { for k, v in var.lambdas : k => {
      route_key = v.route_key
      lambda    = k
    } },
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
# API Gateway Outputs
########################################

output "api_invoke_url" {
  description = "HTTP API invoke URL"
  value       = aws_apigatewayv2_stage.default_stage.invoke_url
}
