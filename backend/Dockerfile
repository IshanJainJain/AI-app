FROM python:3.11-slim

WORKDIR /app

# System deps — gcc+curl: compiler for any native wheels, curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Ensure all package __init__.py files exist
RUN touch app/__init__.py app/api/__init__.py app/api/routes/__init__.py \
         app/db/__init__.py app/agents/__init__.py app/mcp/__init__.py \
         app/rag/__init__.py app/memory/__init__.py app/guardrails/__init__.py \
         app/telemetry/__init__.py app/workers/__init__.py

# Knowledge base volume mount point
RUN mkdir -p knowledge_base

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
