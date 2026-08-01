import sys
import time
import random
import logging
import argparse
from common.job_status_client import JobStatusClient, HeartbeatThread

logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Simulated TA Job")
    parser.add_argument("symbol", help="Crypto symbol")
    parser.add_argument("timeframe", help="Timeframe")
    parser.add_argument("job_id", help="Job ID")
    parser.add_argument("--block", type=int, help="Seconds to simulate a heavy blocking task")

    args = parser.parse_args()

    logger.info("Starting job %s for %s (%s)", args.job_id, args.symbol, args.timeframe)

    try:
        # Initialize the client
        client = JobStatusClient()

        # Start the heartbeat thread
        heartbeat_thread = HeartbeatThread(client, args.job_id, interval=30)
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
                client.report_progress(args.job_id, progress)

            logger.info("Job completed successfully!")
            client.complete_job(args.job_id)

        finally:
            # Ensure heartbeat thread is stopped even if job fails or is interrupted
            heartbeat_thread.stop()
            heartbeat_thread.join()

    except Exception as e:
        logger.error("Job failed: %s", str(e))
        try:
            if client:
                client.fail_job(args.job_id, str(e))
        except Exception as client_err:
            logger.error("Failed to report job failure: %s", str(client_err))
        sys.exit(1)

if __name__ == "__main__":
    main()
