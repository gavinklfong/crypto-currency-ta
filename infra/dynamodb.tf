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
# DynamoDB Table for Job Tracking
########################################

resource "aws_dynamodb_table" "job_tracker" {
  name         = var.job_tracker_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  # PK: JOB#{job_id}
  # SK: METADATA

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "last_heartbeat"
    type = "S"
  }

  attribute {
    name = "instance_id"
    type = "S"
  }

  attribute {
    name = "start_time"
    type = "S"
  }

  # GSI for monitoring stalled jobs (Requirement 2)
  # Allows querying for all RUNNING jobs where last_heartbeat is old.
  global_secondary_index {
    name               = "StatusHeartbeatIndex"
    hash_key           = "status"
    range_key          = "last_heartbeat"
    projection_type    = "ALL"
  }

  # GSI for querying jobs by status ordered by creation time (Requirement 1)
  global_secondary_index {
    name               = "StatusStartTimeIndex"
    hash_key           = "status"
    range_key          = "start_time"
    projection_type    = "ALL"
  }

  # GSI for instance history
  global_secondary_index {
    name               = "InstanceHistoryIndex"
    hash_key           = "instance_id"
    range_key          = "start_time"
    projection_type    = "ALL"
  }

  tags = {
    Name        = var.job_tracker_table_name
    Environment = "development"
    Purpose     = "Tracking EC2 job execution and heartbeats"
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

output "job_tracker_table_name" {
  description = "Name of the DynamoDB table for job tracking"
  value       = aws_dynamodb_table.job_tracker.name
}

output "job_tracker_table_arn" {
  description = "ARN of the DynamoDB table for job tracking"
  value       = aws_dynamodb_table.job_tracker.arn
}
