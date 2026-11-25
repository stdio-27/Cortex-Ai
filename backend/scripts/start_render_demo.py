"""Run the API and a one-slot Celery worker in Render's free web container."""

import os
import signal
import subprocess
import time


def main() -> int:
    stopping = False

    def request_shutdown(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)
    commands = (
        ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", os.getenv("PORT", "10000")],
        ["celery", "-A", "app.worker.celery_app", "worker", "--loglevel=info", "--concurrency=1"],
    )
    child_identity = {"user": 10001, "group": 10001, "extra_groups": []} if os.geteuid() == 0 else {}
    children: list[subprocess.Popen] = []
    try:
        for command in commands:
            if stopping:
                return 0
            children.append(subprocess.Popen(command, **child_identity))
        while not stopping:
            for child in children:
                if child.poll() is not None:
                    print(f"{child.args[0]} exited with status {child.returncode}", flush=True)
                    return 1
            time.sleep(0.25)
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        deadline = time.monotonic() + 20
        for child in children:
            try:
                child.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
