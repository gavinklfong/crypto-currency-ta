provider "aws" {
  region = "us-east-2"
}

# Lambda function and execution role
resource "aws_iam_role" "lambda_exec" {
  name = "hello-world-lambda-exec"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "hello_world" {
  function_name = "hello-world-lambda-updated-2"
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"

  filename         = "${path.module}/../deployment.zip"
  source_code_hash = filebase64sha256("${path.module}/../deployment.zip")

  role = aws_iam_role.lambda_exec.arn
}
