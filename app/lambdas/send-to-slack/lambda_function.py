import json
import os
import urllib.request

def lambda_handler(event, context):
    # SNS event structure: event['Records'][0]['Sns']['Message']
    try:
        message = event['Records'][0]['Sns']['Message']
    except (KeyError, IndexError) as e:
        print(f"Error parsing SNS event: {e}")
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Invalid SNS event structure'})
        }

    webhook_url = os.environ.get('SLACK_WEBHOOK_URL')
    if not webhook_url:
        print("Error: SLACK_WEBHOOK_URL environment variable is not set.")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'SLACK_WEBHOOK_URL not set'})
        }

    slack_data = {
        "text": message
    }

    try:
        data = json.dumps(slack_data).encode('utf-8')
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req) as response:
            status_code = response.getcode()
            if status_code >= 200 and status_code < 300:
                print(f"Successfully sent message to Slack. Status: {status_code}")
                return {
                    'statusCode': 200,
                    'body': json.dumps({'message': 'Sent to Slack successfully'})
                }
            else:
                print(f"Failed to send message to Slack. Status: {status_code}")
                return {
                    'statusCode': status_code,
                    'body': json.dumps({'error': f'Slack returned status {status_code}'})
                }
    except Exception as e:
        print(f"Error sending message to Slack: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
