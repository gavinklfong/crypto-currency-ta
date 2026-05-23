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

variable "extra_routes" {
  description = "Additional routes that reuse existing Lambdas"
  type = map(object({
    route_key = string
    lambda    = string
  }))
  default = {
    root = {
      route_key = "GET /"
      lambda    = "fetch_market_data"
    }
  }
}


variable "symbols" {
  description = "List of trading symbols to track"
  type        = list(string)
  default     = ["XXBTZUSD", "XETHZUSD"]
}

variable "timeframe_schedules" {
  description = "Mapping of timeframe identifiers to CloudWatch rate expressions"
  type        = map(string)
  default = {
    "1m"  = "rate(1 minute)"
    "5m"  = "rate(1 minute)"
    "15m" = "rate(1 minute)"
    "30m" = "rate(1 minute)"
    "1h"  = "rate(5 minutes)"
    "4h"  = "rate(5 minutes)"
    "1d"  = "rate(5 minutes)"
    "1w"  = "rate(5 minutes)"
  }
}

variable "lambdas" {
  description = "Lambda configurations with timeframe subscriptions"
  type = map(object({
    function_name = string
    zip_path      = string
    route_key     = optional(string)
    timeframes    = list(string)

  }))
  default = {
    fetch_market_data = {
      function_name = "fetch-market-data"
      zip_path      = "../.package/deployment-fetch-market-data.zip"
      route_key     = "GET /trigger-fetch-market-data"
      timeframes    = ["1m"]
    }

    calculate_ta = {
      function_name = "calculate-ta"
      zip_path      = "../.package/deployment-calculate-ta.zip"
      timeframes    = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
    }

    aggregate_timeframe = {
      function_name = "aggregate-timeframe"
      zip_path      = "../.package/deployment-aggregate-timeframe.zip"
      timeframes    = ["5m", "15m", "30m", "1h", "4h", "1d", "1w"]
    }
  }
}
