import os
import boto3

_sns_client = None

def _get_sns_client():
    global _sns_client
    if _sns_client is None:
        _sns_client = boto3.client("sns")
    return _sns_client

def send_to_sns(text: str, topic_arn: str = None) -> dict:
    """Publish a message to an SNS topic.

    Args:
        text: The message text to publish.
        topic_arn: The SNS topic ARN. Defaults to the SNS_TOPIC_ARN env var.

    Returns:
        The SNS publish response.
    """
    if topic_arn is None:
        topic_arn = os.environ["SNS_TOPIC_ARN"]

    client = _get_sns_client()
    return client.publish(
        TopicArn=topic_arn,
        Message=text
    )
