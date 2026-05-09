########################################
# Local Variables
########################################

locals {
  timestream_database_name = "crypto-price-database"
  timestream_table_name    = "price-data"
}

########################################
# AWS Timestream Database
########################################

resource "aws_timestreamwrite_database" "crypto_db" {
  database_name = local.timestream_database_name

  tags = {
    Name        = "crypto-price-database"
    Environment = "production"
  }
}

########################################
# AWS Timestream Table
########################################

resource "aws_timestreamwrite_table" "crypto_table" {
  database_name = aws_timestreamwrite_database.crypto_db.database_name
  table_name    = local.timestream_table_name

  retention_properties {
    magnetic_store_retention_period_in_days = 365
    memory_store_retention_period_in_hours  = 24
  }

  tags = {
    Name        = "crypto-price-data"
    Environment = "production"
  }
}

########################################
# IAM Policy for Lambda to access Timestream
########################################

resource "aws_iam_role_policy" "lambda_timestream" {
  name = "lambda-timestream-policy"
  role = aws_iam_role.lambda_exec.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "timestream:WriteRecords",
          "timestream:DescribeDatabase",
          "timestream:DescribeTable",
          "timestream:ListDatabases",
          "timestream:ListTables"
        ]
        Resource = [
          aws_timestreamwrite_database.crypto_db.arn,
          "${aws_timestreamwrite_table.crypto_table.arn}*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "timestream:CreateDatabase",
          "timestream:CreateTable"
        ]
        Resource = "arn:aws:timestream:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:database/*"
      }
    ]
  })
}

########################################
# Data sources for account and region info
########################################

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

########################################
# Outputs
########################################

output "timestream_database_name" {
  value       = aws_timestreamwrite_database.crypto_db.database_name
  description = "Name of the Timestream database"
}

output "timestream_database_arn" {
  value       = aws_timestreamwrite_database.crypto_db.arn
  description = "ARN of the Timestream database"
}

output "timestream_table_name" {
  value       = aws_timestreamwrite_table.crypto_table.table_name
  description = "Name of the Timestream table"
}

output "timestream_table_arn" {
  value       = aws_timestreamwrite_table.crypto_table.arn
  description = "ARN of the Timestream table"
}
