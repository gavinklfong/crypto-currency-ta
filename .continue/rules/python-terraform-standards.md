# Python and Terraform Project Standards

## Architecture Context
- This repository manages a serverless backend.
- The Python codebase in `/app/lambdas` houses AWS Lambda processing functions.
- The Python codebase in `/app/layers` houses AWS Lambda layers
- The Terraform infrastructure in `/infra` manages AWS resources, IAM permissions, and deployment pipelines.
- CI/CD pipeline makes use of GitHub Actions with the workflow definition in `.github/workflows/deploy.yaml`
- The CI/CD pipeline makes use of the following utility scripts:
  - `build.py`: A utility script to build and package each lambda function in `/app`
  - `run_tests.py`: a utility script to run automated tests of each lambda function in `/app/lambdas`

## Coding & Tooling Standards
- **Python:** Use Python 3.11+. Focus on memory-optimized, vectorized Pandas code. Keep packaging footprints minimal to respect AWS Lambda layer zip deployment limits.
- **Terraform:** Always format files utilizing `terraform fmt`. Use strict module variables and resource tagging policies.

## Documentation Resources
When navigating architecture planning or generating changes, reference these patterns and official APIs:
- AWS Lambda Python Developer Guide: https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html
- Terraform AWS Provider Documentation: https://registry.terraform.io/providers/hashicorp/aws/latest/docs
- Pandas Vectorization Best Practices: https://pandas.pydata.org/docs/user_guide/10min.html

Always cite these documentation structures or matching patterns from our local code files when proposing structural architecture refactors.