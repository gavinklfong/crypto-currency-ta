resource "aws_cloudwatch_event_rule" "ec2_job_trigger" {
  name        = "ec2-job-trigger"
  description = "Trigger for long-running EC2 TA jobs"

  event_pattern = jsonencode({
    source      = ["my.crypto.ta.app"]
    detail-type = ["start-long-running-job"]
  })
}

resource "aws_cloudwatch_event_target" "ec2_job_launcher_target" {
  rule      = aws_cloudwatch_event_rule.ec2_job_trigger.name
  target_id = "ec2-job-launcher"
  arn       = aws_lambda_function.lambda["ec2-job-launcher"].arn
}

resource "aws_lambda_permission" "allow_ec2_job_trigger" {
  statement_id  = "AllowEventBridgeToInvokeEC2JobLauncher"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.lambda["ec2-job-launcher"].function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.ec2_job_trigger.arn
}
