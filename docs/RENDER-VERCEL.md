# Deploy Cortex AI on Render, Atlas, and Vercel

## 1. Prepare Atlas

Create a cluster and a database user with `readWrite` on `research_copilot` and `checkpointing_db`. LangGraph uses the second database to persist plans and resume checkpoints. In Atlas, open **Connect → Drivers** and copy the `mongodb+srv://` URI. Replace the password placeholder with the URL-encoded database password.

In Atlas **Network Access**, allow the outbound CIDRs of your Render web service. The Blueprint places the web service and Key Value in Oregon. After Render creates the web service, find its exact CIDRs under **Connect → Outbound**. If the first deploy starts before the Atlas rules are ready, add the rules and redeploy the web service.

## 2. Create the Render Blueprint

Push the repository and select **New → Blueprint** in Render. The root `render.yaml` provisions one free Docker web service and one free private Key Value instance. The web container starts FastAPI and a single-slot Celery worker. Render's free tier spins the web service down after 15 minutes of inactivity, pausing the worker as well. Key Value is in-memory only, so a Redis restart can lose queued jobs and SSE snapshots. Atlas keeps reports and checkpoints across service restarts. This setup is intended for demos.

| Service | Environment variable | Value |
| --- | --- | --- |
| Web | `MONGODB_URI` | The Atlas Drivers URI |
| Web | `GROQ_API_KEY` | Create in the GroqCloud Console under **API Keys** |
| Web | `TAVILY_API_KEY` | Copy from your Tavily dashboard |
| Web | `CORS_ORIGINS` | `https://<your-vercel-project>.vercel.app` or your intended frontend origin. Use the localhost defaults temporarily if the domain is unknown. |

The Blueprint sets `MONGODB_DB_NAME=research_copilot`, `GROQ_MODEL=openai/gpt-oss-20b`, `GROQ_FAST_MODEL=openai/gpt-oss-20b`, and `MOCK_LLM_FOR_LOAD_TEST=false`. Render supplies `PORT` and wires `REDIS_URI` from Key Value. Leave `REDIS_PUBSUB_URI` unset to share the same connection URL. A `rediss://` URL uses certificate and hostname verification.

Copy the web service URL after it deploys. Check `/health` for process liveness, `/api/health/ready` for MongoDB and Redis connectivity, and the web service logs for Celery readiness. The broker uses `noeviction` so memory pressure surfaces as write errors instead of silently evicting queued work.

## 3. Deploy the frontend on Vercel

Import the same repository, set **Root Directory** to `frontend`, and select the **Vite** preset. In the Vercel **Production** environment, add:

```text
VITE_API_BASE_URL=https://<your-render-web-service>.onrender.com
```

Use the web service origin without `/api`. Vite puts this URL in the browser bundle. Keep provider credentials on Render. Deploy the frontend, copy its exact HTTPS origin, and update `CORS_ORIGINS` on the Render web service. Run one job from the Vercel site through plan approval to the final report and confirm the browser's EventSource connects directly to Render.

The split deployment exposes the Render API on the internet. CORS restricts browser origins. API authentication and per-user quotas are required before publishing this as an open service with live provider keys. The single-host Compose deployment has a shared Caddy login and is documented separately in [DEPLOYMENT.md](DEPLOYMENT.md).
