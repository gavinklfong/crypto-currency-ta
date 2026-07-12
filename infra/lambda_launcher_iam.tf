# IAM Role for Lambda Launcher
resource "aws_iam_role" "lambda_launcher_role" {
  name = "crypto-currency-ta-lambda-launcher-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      },
    ]
  })

  tags = {
    Name        = "crypto-currency-ta-lambda-launcher-role"
    Environment = "development"
  }
}

# Policy for launching EC2 instances
resource "aws_iam_role_policy" "lambda_launcher_policy" {
  name = "crypto-currency-ta-lambda-launcher-policy"
  role = aws_iam_role.lambda_launcher_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "ec2:RunInstances",
          "ec2:TerminateInstances",
          "ec2:DescribeInstances"
        ]
        Effect   = "Allow"
        Resource = "*"
      },
      {
        Action = [
          "iam:PassRole"
        ]
        Effect   = "Allow"
        Resource = [aws_iam_role.ec2_worker_role.arn]
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

# Attach basic execution policy for CloudWatch logs
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_launcher_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
