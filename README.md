# Cortex AI - Autonomous Research Copilot

![CI Pipeline](https://github.com/yourusername/cortex/actions/workflows/ci.yml/badge.svg)

Cortex AI is an autonomous, multi-agent research copilot that processes user queries, breaks them down into targeted sub-topics, searches the web, sanitizes data, and iteratively synthesizes a comprehensive report through a critique-driven agent loop.

## Architecture

### High-Level Infrastructure & Decoupled Data Flow
```mermaid
flowchart TD
    %% Client Layer
    subgraph ClientLayer [Client Layer]
        UI[React/Vite UI\nPort: 5173]
    end

    %% API Gateway Layer
    subgraph WebLayer [API Gateway / Web Layer]
        FastAPI[FastAPI Web Server\nPort: 8000]
    end

    %% Broker & Streaming Layer
    subgraph BrokerLayer [Broker & Streaming Layer]
        Redis[(Redis\nPort: 6379\nBroker & Pub/Sub)]
    end

    %% Persistence Layer
    subgraph PersistenceLayer [Persistence Layer]
        MongoDB[(MongoDB\nPort: 27017\nDurable State)]
    end

    %% Compute Worker Layer
    subgraph WorkerLayer [Compute Worker Layer]
        CeleryWorker[Celery Worker\nLangGraph Engine]
    end

    %% External Integrations
    subgraph External [External Integrations]
        GroqAPI(Groq LLM API\nopenai/gpt-oss-120b/20b)
        TavilyAPI(Tavily Search API)
    end

    %% Relationships and Data Flow
    UI -- "HTTP POST /api/jobs" --> FastAPI
    UI <-- "Server-Sent Events (SSE)\n/api/jobs/{id}/stream" --- FastAPI

    FastAPI -- "Create initial Job\n(Pydantic v2 validation)" --> MongoDB
    FastAPI -- "Dispatch Celery Task" --> Redis

    Redis -- "Task Broker" --> CeleryWorker
    CeleryWorker -- "Update Job State &\nSave Synthesized Report" --> MongoDB

    CeleryWorker -- "Agentic Inference" --> GroqAPI
    CeleryWorker -- "Query Fan-out" --> TavilyAPI

    CeleryWorker -- "Publish State/Token\nEvents (job_updates:{id})" --> Redis
    Redis -- "Stream live events" --> FastAPI
```

### LangGraph Agent Execution & Decision Cycle
```mermaid
stateDiagram-v2
    direction TB

    %% Entry point
    [*] --> sanitization_node : Ingress (Input Defense)

    %% Nodes
    state "sanitization_node" as sanitization_node
    state "planner_node" as planner_node
    state "tavily_node\n(Parallel Search Tasks)" as tavily_node
    state "synthesis_node" as synthesis_node
    state "critique_node" as critique_node
    state "Circuit Breaker / Loop Decision" as decision <<choice>>

    %% Data Flow
    sanitization_node --> planner_node : Clean Input / Query Decomposition
    planner_node --> tavily_node : Sub-goals & Queries
    tavily_node --> synthesis_node : Intermediate Draft Assembly\n(Parallel Results)
    synthesis_node --> critique_node : Draft Report Quality Evaluation
    critique_node --> decision : Evaluation Result

    %% Conditional Edges
    decision --> planner_node : REVISE and iteration < MAX_ITERATIONS
    decision --> synthesis_node : REVISE and iteration < MAX_ITERATIONS\n(Alternative route)
    decision --> [*] : APPROVED or iteration >= MAX_ITERATIONS\n(Circuit Breaker)

    %% Event Publishing Notes
    note right of sanitization_node : Publish Status -> Redis Pub/Sub
    note right of planner_node : Publish Status -> Redis Pub/Sub
    note right of tavily_node : Publish Status -> Redis Pub/Sub
    note right of synthesis_node : Publish Status & Tokens -> Redis Pub/Sub
    note right of critique_node : Publish Status -> Redis Pub/Sub
```

## Key Engineering Highlights

- **Multi-Agent Critique Loops:** Utilizes LangGraph to implement a dynamic cyclic graph where a Planner, Searcher, Synthesizer, and Critic iteratively refine research reports. A circuit breaker ensures the graph halts upon receiving an "APPROVED" critique or reaching maximum iterations.
- **Prompt Sanitization Boundary:** Implements a dedicated sanitization node to strip HTML tags, system prompt injection attempts, and noise from raw search results before passing data to the synthesizer.
- **Centralized Connection Pooling:** Maintains highly concurrent async and sync Redis connection pools with `max_connections=2000`, supporting robust pub/sub and task queuing under heavy load.
- **Real-Time SSE Streaming:** Delivers low-latency status updates to the React UI via Server-Sent Events (SSE), bridging FastAPI streaming responses with Redis pub/sub channels.

## Quickstart & Setup

### Running via Docker Compose

1. Clone the repository and configure your environment:
   ```bash
   cp backend/.env.example backend/.env
   # Ensure you set GROQ_API_KEY and TAVILY_API_KEY in the .env file.
   ```
2. Build and start the services:
   ```bash
   docker compose up --build -d
   ```
3. Access the React UI at `http://localhost:5173`.
4. The FastAPI Swagger docs are available at `http://localhost:8000/docs`.

### Running Tests

The backend test suite uses `pytest`, `pytest-asyncio`, and `httpx`, with mocked dependencies to run quickly without external services.

```bash
cd backend
pip install -r requirements.txt
pytest tests/ --cov=app --cov-report=term
```

### Concurrency & Load Testing

A robust Locust test suite is provided to validate backend concurrency (e.g., simulating 1000+ concurrent users). To run the load tests without consuming actual LLM API credits:

1. Enable mock mode by setting the environment variable in the terminal where you run Locust, or in your `.env` (if supported by your setup):
   ```bash
   export MOCK_LLM_FOR_LOAD_TEST=true
   ```
2. Start the Locust server:
   ```bash
   cd load_testing
   locust -f locustfile.py
   ```
3. Open `http://localhost:8089` to configure and start the simulated load.

## License

MIT License
