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

locals {
  job_files = merge([
    for job_name, job_path in var.job_scripts : {
      for f in fileset("${path.module}/../${job_path}", "**") :
      "${job_name}/${f}" => "${path.module}/../${job_path}/${f}"
      if !contains(split("/", f), "__pycache__") && !contains(split("/", f), ".pytest_cache") && !endswith(f, ".pyc")
    }
  ]...)
}

resource "aws_s3_object" "job_scripts" {
  for_each = local.job_files

  bucket = aws_s3_bucket.job_scripts.id
  key    = each.key
  source = each.value
  etag   = filemd5(each.value)
}
