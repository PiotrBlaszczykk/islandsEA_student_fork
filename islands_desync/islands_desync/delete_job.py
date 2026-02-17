import sys

from ray.dashboard.modules.job.sdk import JobSubmissionClient

job_to_delete_id = sys.argv[1]

client = JobSubmissionClient("http://127.0.0.1:8265")

if client.stop_job(job_to_delete_id):
    print("Successfully stopped job: %s" % job_to_delete_id)
else:
    print("Failed to stop job: %s" % job_to_delete_id)
