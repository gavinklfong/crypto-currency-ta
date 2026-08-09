"""Launch EC2 job worker for cryptocurrency technical analysis.

Receives EventBridge events with symbol/timeframe/job_script_name,
configures an EC2 instance (on-demand or spot), initializes a job
tracker in DynamoDB, and returns the instance ID for monitoring.
"""

from __future__ import annotations

import base64
import boto3
import json
import logging
from common_utils import log_info, log_error
import os
import uuid
from dataclasses import dataclass
from typing import Any

from common.job_status_client import JobStatusClient

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

INSTANCE_TYPE_MAP: dict[str, str] = {
    "small": "t3.small",
    "medium": "t3.medium",
    "large": "t3.large",
}

# Environment variable names
ENV_LAUNCH_TEMPLATE_ID = "LAUNCH_TEMPLATE_ID"
ENV_JOB_SCRIPTS_BUCKET_NAME = "JOB_SCRIPTS_BUCKET_NAME"
ENV_INSTANCE_TYPE = "INSTANCE_TYPE"
ENV_SPOT_ENABLED = "SPOT_ENABLED"
ENV_SPOT_MAX_PRICE = "SPOT_MAX_PRICE"

# EC2 tags
TAG_MANAGED_BY = "ManagedBy"
TAG_MANAGED_BY_VALUE = "CryptoTA-JobLauncher"
TAG_JOB_ID = "JobId"
TAG_INSTANCE_TYPE_KEY = "InstanceType"
TAG_INSTANCE_TYPE_SPOT = "spot"
TAG_INSTANCE_TYPE_ON_DEMAND = "on-demand"

# UserData constants
USER_DATA_SLEEP_SECONDS = 60

# Default values
DEFAULT_INSTANCE_TYPE_KEY = "small"

# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


@dataclass
class ValidationError:
    """Structured validation error."""

    status_code: int
    message: str


def validate_input(event: dict[str, Any]) -> ValidationError | None:
    """Validate event detail and environment configuration.

    Returns ``None`` when validation passes, otherwise a
    :class:`ValidationError` with the appropriate HTTP status code
    and error message.
    """
    detail = event.get("detail", {})

    if not detail.get("job_payload"):
        return ValidationError(
            status_code=400,
            message="Missing job_payload in event detail",
        )

    if not detail.get("job_script_name"):
        return ValidationError(
            status_code=400,
            message="Missing job_script_name in event detail",
        )

    if not os.environ.get(ENV_LAUNCH_TEMPLATE_ID):
        log_error("Error: %s environment variable is not set.", ENV_LAUNCH_TEMPLATE_ID)
        return ValidationError(
            status_code=500,
            message=f"{ENV_LAUNCH_TEMPLATE_ID} not set",
        )

    if not os.environ.get(ENV_JOB_SCRIPTS_BUCKET_NAME):
        log_error("Error: %s environment variable is not set.", ENV_JOB_SCRIPTS_BUCKET_NAME)
        return ValidationError(
            status_code=500,
            message=f"{ENV_JOB_SCRIPTS_BUCKET_NAME} not set",
        )

    return None


# ------------------------------------------------------------------
# Configuration resolution
# ------------------------------------------------------------------


def resolve_spot_config(event: dict[str, Any]) -> tuple[bool, str]:
    """Resolve spot instance configuration from event detail or environment.

    Returns ``(spot_enabled, spot_max_price)``.
    """
    detail = event.get("detail", {})
    spot_enabled = str(
        detail.get("spot_enabled", os.environ.get(ENV_SPOT_ENABLED, "false"))
    ).lower() == "true"
    spot_max_price = detail.get(
        "spot_max_price", os.environ.get(ENV_SPOT_MAX_PRICE, "")
    )
    return spot_enabled, spot_max_price


def resolve_instance_type(
    event_instance_type_key: str | None,
) -> str:
    """Map a human-readable instance type key to an AWS instance type.

    Falls back to the environment variable ``INSTANCE_TYPE`` and then
    to ``"small"`` if neither is available or valid.
    """
    key = event_instance_type_key or os.environ.get(ENV_INSTANCE_TYPE, DEFAULT_INSTANCE_TYPE_KEY)
    aws_type = INSTANCE_TYPE_MAP.get(key, INSTANCE_TYPE_MAP[DEFAULT_INSTANCE_TYPE_KEY])
    log_info(
        "Selected instance type: %s (from key: %s)",
        aws_type,
        key,
    )
    return aws_type


# ------------------------------------------------------------------
# UserData builder
# ------------------------------------------------------------------


def build_userdata(
    scripts_bucket: str,
    job_script_name: str,
    region: str,
    job_id: str,
    job_payload: str,
) -> str:
    """Build the shell script executed by the EC2 instance on boot.

    The script downloads the job directory and common utilities from
    S3, installs dependencies, runs the job with the provided
    ``job_payload`` as input, waits for log flush, then shuts down.
    """
    return (
        f"#!/bin/bash\n"
        f"# Update and install dependencies\n"
        f"yum update -y\n"
        f"yum install -y python3-pip aws-cli\n\n"

        f"# Download the TA job directory from S3\n"
        f'echo "aws s3 cp s3://{scripts_bucket}/{job_script_name}/ /tmp/{job_script_name}/ --recursive"\n'
        f"aws s3 cp s3://{scripts_bucket}/{job_script_name}/ /tmp/{job_script_name}/ --recursive\n\n"

        f"# Install job-specific dependencies\n"
        f"pip3 install -r /tmp/{job_script_name}/requirements.txt\n\n"

        f"# Download the common utilities from S3\n"
        f'echo "aws s3 cp s3://{scripts_bucket}/common/ /tmp/common/ --recursive"\n'
        f"aws s3 cp s3://{scripts_bucket}/common/ /tmp/common/ --recursive\n\n"

        f"# Install common dependencies\n"
        f"pip3 install -r /tmp/common/requirements.txt\n\n"

        f"# Export PYTHONPATH so common can be found\n"
        f"export PYTHONPATH=$PYTHONPATH:/tmp\n\n"

        f"# Export AWS region for boto3\n"
        f'echo "Setting AWS region to {region}"\n'
        f"export AWS_DEFAULT_REGION={region}\n\n"

        f"# Force unbuffered Python output so logs appear in real-time\n"
        f"export PYTHONUNBUFFERED=1\n\n"

        f"# Export job ID as environment variable\n"
        f"export TA_JOB_ID={job_id}\n\n"

        f"# Execute the TA job main script with job_payload as input\n"
        f"python3 /tmp/{job_script_name}/main.py '{job_payload}'\n\n"

        f"# Upload job log to S3 for persistence\n"
        f"aws s3 cp /tmp/job-${{TA_JOB_ID}}.log s3://{scripts_bucket}/logs/ta-job/${{TA_JOB_ID}}.log --quiet\n\n"

        f"# Sleep to allow logs to flush before shutdown\n"
        f"sleep {USER_DATA_SLEEP_SECONDS}\n\n"

        f"# Shutdown the instance\n"
        f"sudo shutdown -h now\n"
    )


# ------------------------------------------------------------------
# EC2 launch configuration builder
# ------------------------------------------------------------------


def build_launch_kwargs(
    launch_template_id: str,
    instance_type: str,
    user_data: str,
    job_id: str,
    spot_enabled: bool,
    spot_max_price: str,
) -> dict[str, Any]:
    """Build keyword arguments for ``boto3.client('ec2').run_instances``."""
    base_tags = [
        {"Key": TAG_MANAGED_BY, "Value": TAG_MANAGED_BY_VALUE},
        {"Key": TAG_JOB_ID, "Value": job_id},
    ]

    kwargs: dict[str, Any] = {
        "LaunchTemplate": {"LaunchTemplateId": launch_template_id},
        "InstanceType": instance_type,
        "MinCount": 1,
        "MaxCount": 1,
        "UserData": base64.b64encode(user_data.encode("utf-8")).decode("utf-8"),
        "TagSpecifications": [
            {
                "ResourceType": "instance",
                "Tags": base_tags,
            }
        ],
    }

    if spot_enabled:
        kwargs["InstanceMarketOptions"] = {
            "MarketType": "spot",
            "SpotOptions": {
                "MaxPrice": spot_max_price or None,
                "InstanceInterruptionBehavior": "terminate",
                "SpotInstanceType": "one-time",
            },
        }
        kwargs["TagSpecifications"][0]["Tags"].append(
            {"Key": TAG_INSTANCE_TYPE_KEY, "Value": TAG_INSTANCE_TYPE_SPOT}
        )
    else:
        kwargs["TagSpecifications"][0]["Tags"].append(
            {"Key": TAG_INSTANCE_TYPE_KEY, "Value": TAG_INSTANCE_TYPE_ON_DEMAND}
        )

    return kwargs


# ------------------------------------------------------------------
# Lambda handler
# ------------------------------------------------------------------


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point for launching an EC2 job worker.

    Expected event shape::

        {
            "detail": {
                "job_payload": "{\"symbol\": \"XBTUSD\", \"timeframe\": \"1h\"}",
                "job_script_name": "ta-job",
                "instance_type": "large",        # optional
                "spot_enabled": true,             # optional
                "spot_max_price": "0.05",         # optional
            }
        }
    """
    log_info("Received event: %s", json.dumps(event))

    # 1. Validate inputs
    error = validate_input(event)
    if error:
        return {"statusCode": error.status_code, "body": json.dumps({"error": error.message})}

    detail = event.get("detail", {})
    job_script_name: str = detail["job_script_name"]
    job_payload: str = detail["job_payload"]

    # 2. Resolve configuration
    launch_template_id = os.environ[ENV_LAUNCH_TEMPLATE_ID]
    scripts_bucket = os.environ[ENV_JOB_SCRIPTS_BUCKET_NAME]
    instance_type = resolve_instance_type(detail.get("instance_type"))
    spot_enabled, spot_max_price = resolve_spot_config(event)

    log_info("Spot instances: %s", "enabled" if spot_enabled else "disabled")

    # 3. Initialise job tracker
    job_id = str(uuid.uuid4())
    try:
        job_status = JobStatusClient()
        job_status.start_job(
            job_id=job_id,
            job_type=job_script_name,
            instance_id="PENDING",
        )
    except Exception:
        log_error("Failed to initialise job tracker for job %s", job_id, exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to initialise job tracker"}),
        }

    # 4. Build UserData and EC2 launch config
    region = boto3.session.Session().region_name
    userdata = build_userdata(
        scripts_bucket, job_script_name, region, job_id, job_payload,
    )
    launch_kwargs = build_launch_kwargs(
        launch_template_id=launch_template_id,
        instance_type=instance_type,
        user_data=userdata,
        job_id=job_id,
        spot_enabled=spot_enabled,
        spot_max_price=spot_max_price,
    )

    # 5. Launch EC2 instance
    ec2 = boto3.client("ec2")
    log_info(
        "Launching EC2 with template %s, type %s",
        launch_template_id,
        instance_type,
    )

    try:
        response = ec2.run_instances(**launch_kwargs)
        instance_id: str = response["Instances"][0]["InstanceId"]
        log_info("Successfully launched instance: %s", instance_id)

        # Update job tracker with the actual instance_id
        try:
            job_status.table.update_item(
                Key={"PK": f"JOB#{job_id}", "SK": "METADATA"},
                UpdateExpression="SET instance_id = :i",
                ExpressionAttributeValues={":i": instance_id},
            )
        except Exception:
            logger.warning(
                "Failed to update instance_id in job tracker for job %s",
                job_id,
                exc_info=True,
            )

        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "EC2 instance launched successfully",
                "instance_id": instance_id,
                "job_id": job_id,
            }),
        }

    except Exception:
        log_error("Failed to launch EC2 instance for job %s", job_id, exc_info=True)
        try:
            job_status.fail_job(job_id, "EC2 Launch failed")
        except Exception:
            pass

        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Failed to launch EC2 instance"}),
        }
