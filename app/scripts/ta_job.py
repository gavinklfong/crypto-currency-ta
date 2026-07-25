import sys
import time
import random
import argparse
from common.job_status_client import JobStatusClient, HeartbeatThread

def main():
    parser = argparse.ArgumentParser(description="Simulated TA Job")
    parser.add_argument("symbol", help="Crypto symbol")
    parser.add_argument("timeframe", help="Timeframe")
    parser.add_argument("job_id", help="Job ID")
    parser.add_argument("--block", type=int, help="Seconds to simulate a heavy blocking task")

    args = parser.parse_args()

    print(f"Starting job {args.job_id} for {args.symbol} ({args.timeframe})")

    try:
        # Initialize the client
        client = JobStatusClient()

        # Start the heartbeat thread
        heartbeat_thread = HeartbeatThread(client, args.job_id, interval=30)
        heartbeat_thread.start()

        try:
            # If --block is provided, simulate a long-running task that blocks the main thread
            if args.block:
                print(f"Simulating heavy blocking task for {args.block} seconds...")
                # During this time, the main thread is blocked, but the heartbeat thread should continue.
                time.sleep(args.block)
                print("Heavy blocking task finished.")

            # Simulate job work
            for i in range(1, 11):
                progress = i * 10
                print(f"Step {i}/10: Progress {progress}%")

                # Perform "work"
                time.sleep(random.uniform(1, 3))

                # Report progress (heartbeat is now in background)
                client.report_progress(args.job_id, progress)

            print("Job completed successfully!")
            client.complete_job(args.job_id)

        finally:
            # Ensure heartbeat thread is stopped even if job fails or is interrupted
            heartbeat_thread.stop()
            heartbeat_thread.join()

    except Exception as e:
        print(f"Job failed: {str(e)}")
        try:
            client.fail_job(args.job_id, str(e))
        except Exception as client_err:
            print(f"Failed to report job failure: {str(client_err)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
