# IAM Role for EC2 Worker
resource "aws_iam_role" "ec2_worker_role" {
  name = "crypto-currency-ta-ec2-worker-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      },
    ]
  })

  tags = {
    Name        = "crypto-currency-ta-ec2-worker-role"
    Environment = "development"
  }
}

# Policy for DynamoDB and S3 access
resource "aws_iam_role_policy" "ec2_worker_policy" {
  name = "crypto-currency-ta-ec2-worker-policy"
  role = aws_iam_role.ec2_worker_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Effect   = "Allow"
        Resource = [aws_dynamodb_table.market_data.arn, aws_dynamodb_table.job_tracker.arn]
      },
      {
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Effect   = "Allow"
        Resource = [
          aws_s3_bucket.market_data_export.arn,
          "${aws_s3_bucket.market_data_export.arn}/*",
          aws_s3_bucket.job_scripts.arn,
          "${aws_s3_bucket.job_scripts.arn}/*"
        ]
      },
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Attach SSM managed instance core policy for easy access
resource "aws_iam_role_policy_attachment" "ssm_managed_instance_core" {
  role       = aws_iam_role.ec2_worker_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# EC2 Instance Profile
resource "aws_iam_instance_profile" "ec2_worker_profile" {
  name = "crypto-currency-ta-ec2-worker-profile"
  role = aws_iam_role.ec2_worker_role.name
}
