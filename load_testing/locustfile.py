import json
import time
from locust import HttpUser, task, between, events

class JobStreamUser(HttpUser):
    wait_time = between(1, 2)

    @task
    def create_and_stream_job(self):
        # 1. Create a job
        start_time = time.time()
        with self.client.post("/api/jobs", json={"query": "Test load query"}, catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Failed to create job: {response.status_code}")
                return
            try:
                job_id = response.json().get("job_id")
            except Exception as e:
                response.failure(f"Failed to parse job_id: {e}")
                return
        
        # 2. Connect to SSE stream
        stream_url = f"/api/jobs/{job_id}/stream"
        
        with self.client.get(stream_url, stream=True, catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Failed to connect to stream: {response.status_code}")
                return
            
            # Read SSE events
            start_stream_time = time.time()
            try:
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("data:"):
                            data_str = decoded_line.replace("data: ", "").strip()
                            if not data_str:
                                continue
                            data = json.loads(data_str)
                            if data.get("step") in ["DONE", "ERROR"]:
                                break
                response.success()
            except Exception as e:
                response.failure(f"Stream interrupted: {e}")

        # Record SSE duration
        end_time = time.time()
        events.request.fire(
            request_type="SSE",
            name="/api/jobs/[id]/stream",
            response_time=(end_time - start_stream_time) * 1000,
            response_length=0,
            exception=None,
            context={}
        )
