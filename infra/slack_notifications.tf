resource "aws_sns_topic" "slack_notifications" {
  name = "slack-notifications"
}

########################################
# SNS to Lambda Subscription
########################################

resource "aws_sns_topic_subscription" "slack_subscription" {
  topic_arn = aws_sns_topic.slack_notifications.arn
  protocol  = "lambda"
  endpoint  = aws_lambda_function.lambda["send-to-slack"].arn
}

resource "aws_lambda_permission" "allow_sns_to_call_send_to_slack" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda["send-to-slack"].function_name
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.slack_notifications.arn
}
