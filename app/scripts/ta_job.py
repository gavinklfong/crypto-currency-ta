import sys
import time
import random
from common.job_status_client import JobStatusClient

def main():
    if len(sys.argv) < 4:
        print("Usage: python ta_job.py <symbol> <timeframe> <job_id>")
        sys.exit(1)

    symbol = sys.argv[1]
    timeframe = sys.argv[2]
    job_id = sys.argv[3]

    print(f"Starting job {job_id} for {symbol} ({timeframe})")

    try:
        # Initialize the client
        # The table name is passed via environment variable
        client = JobStatusClient()

        # Simulate job work
        for i in range(1, 11):
            progress = i * 10
            print(f"Step {i}/10: Progress {progress}%")

            # Perform "work"
            time.sleep(random.uniform(1, 3))

            # Report progress and heartbeat
            client.report_progress(job_id, progress)
            client.heartbeat(job_id)

        print("Job completed successfully!")
        client.complete_job(job_id)

    except Exception as e:
        print(f"Job failed: {str(e)}")
        try:
            client.fail_job(job_id, str(e))
        except Exception as client_err:
            print(f"Failed to report job failure: {str(client_err)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
