resource "aws_s3_bucket" "market_data_export" {
  bucket = var.export_bucket_name

  tags = {
    Name        = var.export_bucket_name
    Environment = "prod"
    Service     = "dynamodb-market-data-export"
  }
}

resource "aws_s3_bucket_versioning" "market_data_export" {
  bucket = aws_s3_bucket.market_data_export.id

  versioning_configuration {
    status = "Suspended"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "market_data_export" {
  bucket = aws_s3_bucket.market_data_export.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "market_data_export" {
  bucket = aws_s3_bucket.market_data_export.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
