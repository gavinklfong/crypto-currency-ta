
# AI Analysis Lambda (`ai-analysis`)

This Lambda function is responsible for fetching recent market data for a specified cryptocurrency symbol and timeframe, performing technical analysis using an LLM hosted on Amazon Bedrock, and then presenting the analysis.

## 🎯 Purpose
To automate the process of generating technical investment insights by combining market data retrieval with large language model (LLM) reasoning.

## ⚙️ Functionality
The `lambda_handler` executes the following steps:
1.  **Data Retrieval:** Queries DynamoDB (`crypto-currency-ta-market-data`) to fetch the most recent 1-minute OHLCV data and technical indicators (TAs) for a given `symbol` and `timeframe`.
2.  **LLM Invocation:** Prepares a comprehensive prompt with the retrieved data and sends it to the Amazon Bedrock runtime.
3.  **Analysis:** Invokes a powerful model (currently Llama 3.1 70B) to perform a technical analysis, identifying trends, momentum, and support/resistance levels.
4.  **Output:** Logs the final analysis to CloudWatch and returns a structured JSON response.

## 🔌 Dependencies & Configuration
-   **AWS DynamoDB:** Requires a table named `crypto-currency-ta-market-data`.
-   **AWS Bedrock:** Requires the `InvokeModel` permission on the Bedrock service.
-   **Environment:** The function relies on the AWS environment being configured with permissions to access Bedrock and DynamoDB.

## 🧪 Testing Guide

We maintain two types of tests to ensure quality:

### 1. Unit Tests (Recommended Default)
These tests use **mock objects** for Bedrock and DynamoDB, ensuring fast execution and zero API costs.
*   **Command:** `pytest app/lambdas/ai_analysis/test_lambda_function.py`
*   **Purpose:** Verify the logic (data parsing, prompt construction) works correctly without external AWS calls.

### 2. E2E Integration Tests (Live Environment)
These tests execute the code against the **real AWS services**, including DynamoDB and Bedrock.
*   **Command:** `SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXXX/YYYY/MMMM pytest -s -m manual`
*   **🚨 WARNING:** **This will incur real AWS costs and modify real data.** Use this only in a dedicated sandbox environment.
