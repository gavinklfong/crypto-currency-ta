########################################
# DynamoDB Configuration
########################################

variable "dynamodb_table_name" {
  description = "Name of the DynamoDB table for market data"
  type        = string
  default     = "crypto-currency-ta-market-data"
}

########################################
# S3 Configuration
########################################

variable "export_bucket_name" {
  description = "Name of the S3 bucket for exporting market data"
  type        = string
  default     = "crypto-currency-ta-exports"
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
    # root = {
    #   route_key = "GET /"
    #   lambda    = "fetch_market_data"
    # }
  }
}

variable "fifo_queues" {
  description = "Mapping of lambda functions to FIFO SQS queue names"
  type        = map(string)
  default = {
    "fetch-market-data"   = "crypto-currency-ta-fetch-market-data.fifo"
    "calculate-ta"        = "crypto-currency-ta-calculate-ta.fifo"
    "aggregate-timeframe" = "crypto-currency-ta-aggregate-timeframe.fifo"
    "export-data-to-s3"   = "crypto-currency-ta-export-data-to-s3.fifo"
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
    "15m" = "rate(5 minutes)"
    "30m" = "rate(15 minutes)"
    "1h"  = "rate(30 minutes)"
    "4h"  = "rate(1 hour)"
    "1d"  = "rate(4 hours)"
    "1w"  = "rate(1 day)"
  }
}


variable "layers" {
  description = "Lambda layers with their corresponding zip file paths"
  type = map(object({
    layer_name = string
    zip_path   = string
  }))
  default = {
    pandas = {
      layer_name = "pandas"
      zip_path   = "../build/package/layers/pandas.zip"
    }
    pyarrow = {
      layer_name = "pyarrow"
      zip_path   = "../build/package/layers/pyarrow.zip"
    }
  }
}

variable "lambda_controllers" {
  description = "Lambda configurations"
  type = map(object({
    function_name = string
    zip_path      = string
    layers        = optional(list(string), [])
    timeout       = optional(number, 30)
    memory_size   = optional(number)
    route_key     = optional(string)
  }))
  default = {
    "rerun-controller" = {
      function_name = "rerun-controller"
      zip_path      = "../build/package/lambdas/rerun-controller.zip"
    }
  }
}

variable "lambdas" {
  description = "Lambda configurations with timeframe subscriptions and optional schedule overrides per function"
  type = map(object({
    function_name      = string
    zip_path           = string
    layers             = optional(list(string), [])
    timeout            = optional(number, 30)
    memory_size        = optional(number)
    route_key          = optional(string)
    timeframes         = list(string)
    schedule_overrides = optional(map(string), {})
  }))
  default = {

    "fetch-market-data" = {
      function_name = "fetch-market-data"
      zip_path      = "../build/package/lambdas/fetch-market-data.zip"
      # route_key     = "GET /trigger-fetch-market-data"
      timeframes = ["1m"]
    }

    "calculate-ta" = {
      function_name = "calculate-ta"
      zip_path      = "../build/package/lambdas/calculate-ta.zip"
      timeframes    = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"]
    }

    "aggregate-timeframe" = {
      function_name = "aggregate-timeframe"
      zip_path      = "../build/package/lambdas/aggregate-timeframe.zip"
      timeframes    = ["5m", "15m", "30m", "1h", "4h", "1d", "1w"]
    }

    "export-data-to-s3" = {
      function_name = "export-data-to-s3"
      zip_path      = "../build/package/lambdas/export-data-to-s3.zip"
      layers        = ["pandas", "pyarrow"]
      timeout       = 120
      timeframes    = ["1m", "5m", "15m", "30m", "1h", "4h", "1d"]
      # Custom schedule overrides for export function:
      schedule_overrides = {
        "1m"  = "rate(1 hour)"
        "5m"  = "rate(1 hour)"
        "15m" = "rate(1 hour)"
        "30m" = "rate(1 hour)"
        "1h"  = "rate(1 hour)"
        "4h"  = "rate(1 day)"
        "1d"  = "rate(1 day)"
      }
    }
  }
}
