# AWS Required Permissions

The following permissions are required for Terraform to successfully apply the infrastructure changes.

## Amazon API Gateway
- `apigateway:GET`
- `apigateway:POST`
- `apigateway:PUT`
- `apigateway:DELETE`
- `apigateway:PATCH`

## Amazon Bedrock
- `bedrock:InvokeModel`
- `bedrock:InvokeModelWithResponseStream`
- `bedrock:ListFoundationModels`

## Amazon DynamoDB
- `dynamodb:CreateTable`
- `dynamodb:DeleteTable`
- `dynamodb:UpdateTable`
- `dynamodb:DescribeTable`
- `dynamodb:DescribeContinuousBackups`
- `dynamodb:DescribeLimits`
- `dynamodb:DescribeStream`
- `dynamodb:DescribeTimeToLive`
- `dynamodb:ListTables`
- `dynamodb:ListTagsOfResource`
- `dynamodb:TagResource`
- `dynamodb:UntagResource`
- `dynamodb:UpdateContinuousBackups`

## Amazon EventBridge
- `events:PutRule`
- `events:DeleteRule`
- `events:DescribeRule`
- `events:PutTargets`
- `events:RemoveTargets`
- `events:ListTargetsByRule`
- `events:ListTagsForResource`

## AWS IAM
- `iam:CreateRole`
- `iam:DeleteRole`
- `iam:GetRole`
- `iam:UpdateAssumeRolePolicy`
- `iam:PassRole`
- `iam:CreatePolicy`
- `iam:DeletePolicy`
- `iam:GetPolicy`
- `iam:CreatePolicyVersion`
- `iam:DeletePolicyVersion`
- `iam:GetPolicyVersion`
- `iam:AttachRolePolicy`
- `iam:DetachRolePolicy`
- `iam:PutRolePolicy`
- `iam:GetRolePolicy`
- `iam:DeleteRolePolicy`
- `iam:ListAttachedRolePolicies`
- `iam:ListRolePolicies`
- `iam:ListPolicyVersions`

## AWS Lambda
- `lambda:CreateFunction`
- `lambda:DeleteFunction`
- `lambda:GetFunction`
- `lambda:GetFunctionConfiguration`
- `lambda:GetFunctionCodeSigningConfig`
- `lambda:UpdateFunctionCode`
- `lambda:UpdateFunctionConfiguration`
- `lambda:ListFunctions`
- `lambda:AddPermission`
- `lambda:RemovePermission`
- `lambda:PublishVersion`
- `lambda:ListVersionsByFunction`
- `lambda:CreateAlias`
- `lambda:UpdateAlias`
- `lambda:DeleteAlias`
- `lambda:GetAlias`
- `lambda:ListAliases`
- `lambda:PublishLayerVersion`
- `lambda:GetLayerVersion`
- `lambda:DeleteLayerVersion`
- `lambda:ListLayerVersions`
- `lambda:GetLayerVersionPolicy`
- `lambda:ListLayers`
- `lambda:GetEventSourceMapping`
- `lambda:PassCapacityProvider`
- `lambda:ListTags`

## Amazon S3
- `s3:CreateBucket`
- `s3:DeleteBucket`
- `s3:GetBucketLocation`
- `s3:GetBucketAcl`
- `s3:PutBucketAcl`
- `s3:GetBucketWebsite`
- `s3:GetBucketNotification`
- `s3:GetBucketVersioning`
- `s3:PutBucketVersioning`
- `s3:GetBucketTagging`
- `s3:PutBucketTagging`
- `s3:GetBucketCors`
- `s3:PutBucketCors`
- `s3:GetBucketObjectLockConfiguration`
- `s3:PutBucketObjectLockConfiguration`
- `s3:GetLifecycleConfiguration`
- `s3:PutLifecycleConfiguration`
- `s3:GetEncryptionConfiguration`
- `s3:PutEncryptionConfiguration`
- `s3:GetReplicationConfiguration`
- `s3:PutReplicationConfiguration`
- `s3:GetBucketPublicAccessBlock`
- `s3:PutBucketPublicAccessBlock`
- `s3:GetBucketOwnershipControls`
- `s3:GetBucketLogging`
- `s3:PutAccelerateConfiguration`
- `s3:GetAccelerateConfiguration`
- `s3:GetBucketRequestPayment`
- `s3:PutObject`
- `s3:GetObject`
- `s3:DeleteObject`
- `s3:AbortMultipartUpload`
- `s3:ListBucket`
- `s3:ListBucketMultipartUploads`
- `s3:GetBucketPolicy`
- `s3:PutBucketPolicy`

## Amazon SNS
- `sns:CreateTopic`
- `sns:DeleteTopic`
- `sns:GetTopicAttributes`
- `sns:SetTopicAttributes`
- `sns:ListTopics`
- `sns:Subscribe`
- `sns:Unsubscribe`
- `sns:ConfirmSubscription`
- `sns:ListSubscriptions`
- `sns:ListSubscriptionsByTopic`
- `sns:GetSubscriptionAttributes`
- `sns:SetSubscriptionAttributes`
- `sns:ListTagsForResource`

## Amazon SQS
- `sqs:CreateQueue`
- `sqs:DeleteQueue`
- `sqs:GetQueueAttributes`
- `sqs:SetQueueAttributes`
- `sqs:ListQueues`
- `sqs:ListQueueTags`
- `sqs:ListDeadLetterSourceQueues`

## Amazon CloudWatch Logs
- `logs:CreateLogGroup`
- `logs:DeleteLogGroup`
- `logs:DescribeLogGroups`
- `logs:DescribeLogStreams`
- `logs:CreateLogStream`
- `logs:PutLogEvents`
