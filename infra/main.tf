provider "aws" {
  region = "us-east-2"
}


# resource "aws_s3_bucket" "tf_state" {
#   bucket        = "lambda-terraform-state-bucket-164995166068-us-east-2-an"
#   force_destroy = false
# }

# # Remote state configuration
# resource "aws_s3_bucket_versioning" "tf_state_versioning" {
#   bucket = aws_s3_bucket.tf_state.id

#   versioning_configuration {
#     status = "Enabled"
#   }
# }

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
  function_name = "hello-world-lambda"
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.12"

  filename         = "${path.module}/../deployment.zip"
  source_code_hash = filebase64sha256("${path.module}/../deployment.zip")

  role = aws_iam_role.lambda_exec.arn
}
