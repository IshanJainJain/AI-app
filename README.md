# Local AI App

FastAPI app with persistent threads, global context, per-conversation image context, and an Ollama-compatible local LLM backend.

## Move To A VM

Copy this project folder to the VM. Include `history.db` if you want to keep existing conversations, global context, and per-conversation image context.

Install Python dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Install and start Ollama on the VM, then pull Ministral:

```bash
ollama pull ministral
```

Run the app so it is reachable from outside the VM:

```bash
OLLAMA_MODEL=ministral uvicorn main:app --host 0.0.0.0 --port 8000
```

Open the app from your machine:

```text
http://<VM_IP_ADDRESS>:8000
```

## Configuration

The app reads these environment variables:

```text
OLLAMA_URL=http://localhost:11434/api/generate
OLLAMA_MODEL=ministral
OLLAMA_VISION_MODEL=llava:latest
LLM_TIMEOUT_SECONDS=60
```

If Ollama runs on a different machine than the app, set `OLLAMA_URL` to that machine's Ollama API URL.
Use a vision-capable Ollama model for `OLLAMA_VISION_MODEL`, such as `llava:latest`.
Uploaded images are converted to text with the vision model and stored only on the selected conversation.

## Run Locally On Windows

```powershell
$env:OLLAMA_MODEL="ministral"
uvicorn main:app --host 127.0.0.1 --port 8000
```
