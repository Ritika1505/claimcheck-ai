# ClaimCheck AI

ClaimCheck AI checks YouTube videos for advertising and brand-compliance issues.
It downloads and indexes video content with Azure Video Indexer, retrieves
relevant guidance from Azure AI Search, and uses Azure OpenAI to generate an
audit summary and findings.

## Prerequisites

- Python 3.12 or newer
- Azure OpenAI deployment(s)
- Azure AI Search service and index
- Azure Video Indexer account
- Docker with the Compose plugin, for containerized use

Install the Python dependencies from the repository root:

```powershell
python -m pip install -r requirements.txt
```

## Configure Azure services

Copy `.env.example` to `.env` in the repository root:

```powershell
Copy-Item .env.example .env
```

Replace the placeholder values in `.env` with your Azure settings. Do not
commit `.env` or expose its credentials in logs.

The embedding deployment defaults to `text-embedding-3-small`, and the Video
Indexer account name defaults to `project-brand-guardian-001`. The Video
Indexer service uses `DefaultAzureCredential` for Azure Resource Manager
authentication; configure an appropriate Azure credential for the environment
where the app runs. Azure Monitor telemetry is optional and disabled when
`APPLICATIONINSIGHTS_CONNECTION_STRING` is unset.

## Run locally

Start the FastAPI backend in one terminal:

```powershell
uvicorn backend.src.api.server:app --host 0.0.0.0 --port 8000
```

Start the Streamlit frontend in another terminal:

```powershell
streamlit run frontend\app.py
```

Open the UI at `http://localhost:8501`. By default, it connects to the backend
at `http://localhost:8000`. Set `CLAIMCHECK_API_URL` before starting Streamlit
or change the backend URL in the UI sidebar to use another API address.

### API endpoints

- `GET /health` — reports whether the API process is running.
- `POST /audit` — runs an audit for a video URL. Example request:

  ```json
  {
    "video_url": "https://youtu.be/<video-id>"
  }
  ```

  The response contains the session ID, video ID, status, final report, and
  compliance findings. The request is synchronous and may take several minutes.

Interactive API documentation is available at `http://localhost:8000/docs`.

## Index compliance PDFs

Put PDF reference documents in `backend/data/`, then run from the repository
root:

```powershell
python backend\scripts\index_documents.py
```

The script splits PDF text into chunks and uploads them to the configured Azure
AI Search index using the configured Azure OpenAI embedding deployment.

## Run the complete project with Docker Compose

Ensure the root `.env` file is configured, then run from the repository root:

```powershell
docker compose up --build
```

Compose builds the root `Dockerfile` and starts the API and Streamlit UI in
separate containers:

- UI: `http://localhost:8501`
- API: `http://localhost:8000`
- API health: `http://localhost:8000/health`
- API docs: `http://localhost:8000/docs`

The UI reaches the API at `http://backend:8000` over the Compose network. The
published ports bind to localhost. The API container receives Azure settings
from `.env`; `.dockerignore` excludes the file from the image build context.
Stop the services with:

```powershell
docker compose down
```

## Run the CLI sample

From the repository root, run:

```powershell
python main.py
```

This sends the sample YouTube URL configured in `main.py` through the audit
workflow and prints the result in the terminal.
