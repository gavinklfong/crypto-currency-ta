resource "aws_s3_bucket" "ta_job_scripts" {
  bucket = var.ta_job_scripts_bucket_name

  tags = {
    Name        = var.ta_job_scripts_bucket_name
    Environment = "prod"
    Service     = "ta-job-scripts"
  }
}

resource "aws_s3_bucket_public_access_block" "ta_job_scripts" {
  bucket = aws_s3_bucket.ta_job_scripts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "ta_job_scripts" {
  bucket = aws_s3_bucket.ta_job_scripts.id

  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "ta_job_scripts" {
  bucket = aws_s3_bucket.ta_job_scripts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_object" "ta_job_script" {
  bucket = aws_s3_bucket.ta_job_scripts.id
  key    = "ta_job.py"
  source = "${path.module}/../app/scripts/ta_job.py"
  etag   = filemd5("${path.module}/../app/scripts/ta_job.py")
}
