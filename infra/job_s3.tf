resource "aws_s3_bucket" "job_scripts" {
  bucket = var.job_scripts_bucket_name

  tags = {
    Name        = var.job_scripts_bucket_name
    Environment = "prod"
    Service     = "ta-job-scripts"
  }
}

resource "aws_s3_bucket_public_access_block" "job_scripts" {
  bucket = aws_s3_bucket.job_scripts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "job_scripts" {
  bucket = aws_s3_bucket.job_scripts.id

  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "job_scripts" {
  bucket = aws_s3_bucket.job_scripts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_object" "job_scripts" {
  for_each = var.job_scripts

  bucket = aws_s3_bucket.job_scripts.id
  key    = each.key
  source = "${path.module}/../${each.value}"
  etag   = filemd5("${path.module}/../${each.value}")
}
