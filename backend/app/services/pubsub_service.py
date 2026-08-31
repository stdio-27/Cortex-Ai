import json

class PubSubService:
    def __init__(self, redis_client):
        self.redis_client = redis_client

    def publish_update(self, job_id: str, step_name: str, status: str) -> None:
        try:
            self.redis_client.publish(
                f"job_updates:{job_id}",
                json.dumps({"job_id": job_id, "step": step_name, "status": status})
            )
        except Exception as e:
            print(f"Redis publish error: {e}")

class MockPubSubService:
    def publish_update(self, job_id: str, step_name: str, status: str) -> None:
        pass
