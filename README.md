# Local AI App

FastAPI app with persistent threads, global context, and an Ollama-compatible local LLM backend.

## Move To A VM

Copy this project folder to the VM. Include `history.db` if you want to keep existing conversations and global context.

Install Python dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install and start Ollama on the VM, then pull Devstral:

```bash
ollama pull devstral
```

Run the app so it is reachable from outside the VM:

```bash
OLLAMA_MODEL=devstral uvicorn main:app --host 0.0.0.0 --port 8000
```

Open the app from your machine:

```text
http://<VM_IP_ADDRESS>:8000
```

## Configuration

The app reads these environment variables:

```text
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=devstral
LLM_TIMEOUT_SECONDS=60
```

If Ollama runs on a different machine than the app, set `OLLAMA_URL` to that machine's Ollama API URL.

## Run Locally On Windows

```powershell
$env:OLLAMA_MODEL="devstral"
uvicorn main:app --host 127.0.0.1 --port 8000
```
