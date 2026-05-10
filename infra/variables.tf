########################################
# DynamoDB Configuration
########################################

variable "dynamodb_table_name" {
  description = "Name of the DynamoDB table for market data"
  type        = string
  default     = "crypto-currency-ta-market-data"
}

########################################
# API gateway Configuration
########################################

variable "api_gateway_name" {
  description = "Name of the HTTP API Gateway"
  type        = string
  default     = "crypto-currency-ta-http-api"
}

########################################
# Lambda Configuration
########################################

variable "lambda_exec_role_name" {
  description = "Name of the IAM role for Lambda execution"
  type        = string
  default     = "crypto-currency-ta-lambda-exec"
}

variable "lambdas" {
  description = "Lambda function configurations"
  type = map(object({
    function_name = string
    zip_path      = string
    route_key     = string
  }))
  default = {
    hello1 = {
      function_name = "crypto-currency-ta-lambda-1"
      zip_path      = "../.package/deployment-function-1.zip"
      route_key     = "GET /hello-1"
    }
    hello2 = {
      function_name = "crypto-currency-ta-lambda-2"
      zip_path      = "../.package/deployment-function-2.zip"
      route_key     = "GET /hello-2"
    }
  }
}

variable "extra_routes" {
  description = "Additional routes that reuse existing Lambdas"
  type = map(object({
    route_key = string
    lambda    = string
  }))
  default = {
    root = {
      route_key = "GET /"
      lambda    = "hello1"
    }
  }
}
