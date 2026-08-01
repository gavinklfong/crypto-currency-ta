import sys
import time
import random
import logging
import argparse
from common.job_status_client import JobStatusClient, HeartbeatThread

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    # Read job ID from environment variable
    job_id = os.environ.get("TA_JOB_ID")
    if not job_id:
        logger.error("TA_JOB_ID environment variable is not set")
        sys.exit(1)

    # Parse job params from first command-line argument (JSON)
    if len(sys.argv) < 2:
        logger.error("Missing job params JSON argument")
        sys.exit(1)

    try:
        params = json.loads(sys.argv[1])
        symbol = params["symbol"]
        timeframe = params["timeframe"]
    except (json.JSONDecodeError, KeyError) as e:
        logger.error("Invalid job params JSON: %s", str(e))
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Simulated TA Job")
    parser.add_argument("--block", type=int, help="Seconds to simulate a heavy blocking task")

    args = parser.parse_args()

    logger.info("Starting job %s for %s (%s)", job_id, symbol, timeframe)

    try:
        # Initialize the client
        client = JobStatusClient()

        # Start the heartbeat thread
        heartbeat_thread = HeartbeatThread(client, job_id, interval=30)
        heartbeat_thread.start()

        try:
            # If --block is provided, simulate a long-running task that blocks the main thread
            if args.block:
                logger.info("Simulating heavy blocking task for %s seconds...", args.block)
                # During this time, the main thread is blocked, but the heartbeat thread should continue.
                time.sleep(args.block)
                logger.info("Heavy blocking task finished.")

            # Simulate job work
            for i in range(1, 11):
                progress = i * 10
                logger.info("Step %d/10: Progress %d%%", i, progress)

                # Perform "work"
                time.sleep(random.uniform(1, 3))

                # Report progress (heartbeat is now in background)
                client.report_progress(job_id, progress)

            logger.info("Job completed successfully!")
            client.complete_job(job_id)

        finally:
            # Ensure heartbeat thread is stopped even if job fails or is interrupted
            heartbeat_thread.stop()
            heartbeat_thread.join()

    except Exception as e:
        logger.error("Job failed: %s", str(e))
        try:
            if client:
                client.fail_job(job_id, str(e))
        except Exception as client_err:
            logger.error("Failed to report job failure: %s", str(client_err))
        sys.exit(1)

if __name__ == "__main__":
    main()
