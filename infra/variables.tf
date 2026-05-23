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
    route_key     = optional(string)
    schedule      = optional(string) # e.g. "rate(1 minute)"
    event_input   = any              # JSON event data to pass to Lambda
  }))
  default = {
    fetch_market_data = {
      function_name = "fetch-market-data"
      zip_path      = "../.package/deployment-fetch-market-data.zip"
      route_key     = "GET /trigger-fetch-market-data"
      schedule      = "rate(1 minute)"
      # Pass cryptocurrency symbols to the Lambda without hardcoding
      event_input = {
        detail = {
          symbol = "XXBTZUSD"
        }
      }
    }
    calculate_ta = {
      function_name = "calculate-ta"
      zip_path      = "../.package/deployment-calculate-ta.zip"
      event_input   = {}
    }

    aggregate_timeframe_5m = {
      function_name = "aggregate-timeframe-5m"
      zip_path      = "../.package/deployment-aggregate-timeframe.zip"
      schedule      = "rate(1 minute)"
      event_input = {
        detail = {
          symbol    = "XXBTZUSD"
          timeframe = "5m"
        }
      }
    }
    aggregate_timeframe_15m = {
      function_name = "aggregate-timeframe-15m"
      zip_path      = "../.package/deployment-aggregate-timeframe.zip"
      schedule      = "rate(15 minutes)"
      event_input = {
        detail = {
          symbol    = "XXBTZUSD"
          timeframe = "15m"
        }
      }
    }
    aggregate_timeframe_30m = {
      function_name = "aggregate-timeframe-30m"
      zip_path      = "../.package/deployment-aggregate-timeframe.zip"
      schedule      = "rate(15 minutes)"
      event_input = {
        detail = {
          symbol    = "XXBTZUSD"
          timeframe = "30m"
        }
      }
    }
    aggregate_timeframe_1h = {
      function_name = "aggregate-timeframe-1h"
      zip_path      = "../.package/deployment-aggregate-timeframe.zip"
      schedule      = "rate(30 minutes)"
      event_input = {
        detail = {
          symbol    = "XXBTZUSD"
          timeframe = "1h"
        }
      }
    }
    aggregate_timeframe_1w = {
      function_name = "aggregate-timeframe-1w"
      zip_path      = "../.package/deployment-aggregate-timeframe.zip"
      schedule      = "rate(3 days)"
      event_input = {
        detail = {
          symbol    = "XXBTZUSD"
          timeframe = "1w"
        }
      }
    }
    aggregate_timeframe_1M = {
      function_name = "aggregate-timeframe-1M"
      zip_path      = "../.package/deployment-aggregate-timeframe.zip"
      schedule      = "rate(15 days)"
      event_input = {
        detail = {
          symbol    = "XXBTZUSD"
          timeframe = "1M"
        }
      }
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
      lambda    = "fetch_market_data"
    }
  }
}
