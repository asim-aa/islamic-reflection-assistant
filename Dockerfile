# Container for backend/main.py (the FastAPI backend), built for Cloud Run
# after Render's free 512MB tier proved too small for the ONNX embedding
# model + onnxruntime + FastAPI stack. Cloud Run lets you configure a
# larger memory limit per revision while still staying in its always-free
# tier for light traffic. See README.md "Deployment" for the full
# gcloud run deploy walkthrough.
#
# Not used by the Streamlit app (app.py) or the frontend -- this image is
# backend-only.

FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Preserves the same relative layout backend/main.py expects at import time
# (it does sys.path.insert(0, "..") to reach src/ as a sibling directory).
COPY backend/ backend/
COPY src/ src/
COPY data/ data/

ENV PORT=8080
EXPOSE 8080

CMD exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
