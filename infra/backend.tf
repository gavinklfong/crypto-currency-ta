terraform {
  backend "s3" {
    bucket  = "lambda-terraform-state-bucket-164995166068-us-east-2-an"
    key     = "lambda/terraform.tfstate"
    region  = "us-east-2"
    encrypt = true
  }
}

