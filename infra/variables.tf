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

    # list of schedule objects
    schedules = optional(
      list(object(
        {
          name        = string
          schedule    = string
          event_input = optional(any)
      })),
      null
    )
  }))
  default = {
    fetch_market_data = {
      function_name = "fetch-market-data"
      zip_path      = "../.package/deployment-fetch-market-data.zip"
      route_key     = "GET /trigger-fetch-market-data"
      schedules = [
        {
          name     = "XXBTZUSD-1m"
          schedule = "rate(1 minute)"
          event_input = {
            detail = {
              symbol = "XXBTZUSD"
            }
          }
        }
      ]
    }

    calculate_ta = {
      function_name = "calculate-ta"
      zip_path      = "../.package/deployment-calculate-ta.zip"
      schedules = [
        {
          name     = "XXBTZUSD-1m"
          schedule = "rate(1 minute)"
          event_input = {
            detail = {
              symbol    = "XXBTZUSD"
              timeframe = "1m"
            }
          }
        },
        {
          name     = "XXBTZUSD-5m"
          schedule = "rate(1 minute)"
          event_input = {
            detail = {
              symbol    = "XXBTZUSD"
              timeframe = "5m"
            }
          }
        },
        {
          name     = "XXBTZUSD-15m"
          schedule = "rate(5 minutes)"
          event_input = {
            detail = {
              symbol    = "XXBTZUSD"
              timeframe = "15m"
            }
          }
        },
        {
          name     = "XXBTZUSD-30m"
          schedule = "rate(15 minutes)"
          event_input = {
            detail = {
              symbol    = "XXBTZUSD"
              timeframe = "30m"
            }
          }
        },
        {
          name     = "XXBTZUSD-1h"
          schedule = "rate(30 minutes)"
          event_input = {
            detail = {
              symbol    = "XXBTZUSD"
              timeframe = "1h"
            }
          }
        },
        {
          name     = "XXBTZUSD-4h"
          schedule = "rate(1 hour)"
          event_input = {
            detail = {
              symbol    = "XXBTZUSD"
              timeframe = "4h"
            }
          }
        },
        {
          name     = "XXBTZUSD-1d"
          schedule = "rate(4 hours)"
          event_input = {
            detail = {
              symbol    = "XXBTZUSD"
              timeframe = "1d"
            }
          }
        }
      ]
    }

    aggregate_timeframe = {
      function_name = "aggregate-timeframe"
      zip_path      = "../.package/deployment-aggregate-timeframe.zip"
      schedules = [
        {
          name     = "XXBTZUSD-5m"
          schedule = "rate(1 minute)"
          event_input = {
            detail = {
              symbol    = "XXBTZUSD"
              timeframe = "5m"
            }
          }
        },
        {
          name     = "XXBTZUSD-15m"
          schedule = "rate(5 minutes)"
          event_input = {
            detail = {
              symbol    = "XXBTZUSD"
              timeframe = "15m"
            }
          }
        },
        {
          name     = "XXBTZUSD-30m"
          schedule = "rate(15 minutes)"
          event_input = {
            detail = {
              symbol    = "XXBTZUSD"
              timeframe = "30m"
            }
          }
        },
        {
          name     = "XXBTZUSD-1h"
          schedule = "rate(30 minutes)"
          event_input = {
            detail = {
              symbol    = "XXBTZUSD"
              timeframe = "1h"
            }
          }
        },
        {
          name     = "XXBTZUSD-4h"
          schedule = "rate(1 hour)"
          event_input = {
            detail = {
              symbol    = "XXBTZUSD"
              timeframe = "4h"
            }
          }
        },
        {
          name     = "XXBTZUSD-4d"
          schedule = "rate(1 day)"
          event_input = {
            detail = {
              symbol    = "XXBTZUSD"
              timeframe = "1d"
            }
          }
        }
      ]
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
