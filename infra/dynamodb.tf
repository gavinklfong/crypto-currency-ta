########################################
# DynamoDB Table for Market Data
########################################

resource "aws_dynamodb_table" "market_data" {
  name         = var.dynamodb_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  # DynamoDB schema
  # PK: PAIR#<symbol>
  # SK: TF#<timeframe>#TS#<timestamp>

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  ttl {
    attribute_name = "TTL"
    enabled        = false
  }

  tags = {
    Name        = var.dynamodb_table_name
    Environment = "development"
    Purpose     = "Bitcoin price technical analysis"
  }
}

########################################
# DynamoDB Table Outputs
########################################

output "market_data_table_name" {
  description = "Name of the DynamoDB table for market data"
  value       = aws_dynamodb_table.market_data.name
}

output "market_data_table_arn" {
  description = "ARN of the DynamoDB table for market data"
  value       = aws_dynamodb_table.market_data.arn
}
