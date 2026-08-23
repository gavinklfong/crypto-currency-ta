import sys
import os
import json
import logging
import argparse
from common.job_status_client import JobStatusClient, HeartbeatThread
from warm_start_train import run_training

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    job_id = os.environ.get("TA_JOB_ID")

    if len(sys.argv) < 2:
        logger.error("Missing job params JSON argument")
        if job_id:
            client = JobStatusClient()
            client.fail_job(job_id, "Missing job params JSON argument")
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        symbol = params["symbol"]
        timeframe = params["timeframe"]
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Invalid job params JSON: %s", str(e))
        if job_id:
            client = JobStatusClient()
            client.fail_job(job_id, f"Invalid job params JSON: {e}")
        sys.exit(1)

    sys.argv = sys.argv[:1]

    parser = argparse.ArgumentParser(description="LSTM Warm-Start Training")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    args = parser.parse_args()

    if "dry_run" in params and args.dry_run:
        params["dry_run"] = True

    logger.info("Starting LSTM warm-start job %s for %s (%s)", job_id or "local", symbol, timeframe)

    client = None
    heartbeat_thread = None

    try:
        if job_id:
            client = JobStatusClient()
            heartbeat_thread = HeartbeatThread(client, job_id, interval=30)
            heartbeat_thread.start()
            logger.info("Heartbeat started for job %s (interval=30s)", job_id)

        def on_progress(progress, detail):
            if client and job_id:
                client.report_progress_with_detail(job_id, progress, detail)

        result = run_training(params, on_progress=on_progress)

        if client and job_id:
            client.report_progress_with_detail(job_id, 100, "Training complete")
            client.complete_job(job_id)

        logger.info("Job %s completed successfully", job_id or "local")

    except Exception as e:
        logger.error("Job failed: %s", str(e))
        if client and job_id:
            try:
                client.fail_job(job_id, str(e))
            except Exception as client_err:
                logger.error("Failed to report job failure: %s", str(client_err))
        sys.exit(1)

    finally:
        if heartbeat_thread:
            heartbeat_thread.stop()
            heartbeat_thread.join()


if __name__ == "__main__":
    main()
