# SmartCam cloud control plane (NO PyTorch — detection runs on edge boxes).
#
# Build:  docker build -f api.Dockerfile -t smartcam-api .
# Run:    docker run -p 8000:8000 -e SMART_CAM_CLOUD_ONLY=1 -v smartcam_data:/app/data smartcam-api
#
# Small image, runs in ~256 MB RAM. Fits a 2 GB VPS (and free PaaS tiers).
FROM python:3.11-slim

WORKDIR /app

COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

COPY . .

VOLUME ["/app/data"]

ENV PORT=8000
ENV SMART_CAM_CLOUD_ONLY=1
EXPOSE 8000

CMD ["sh", "-c", "python run_api.py --host 0.0.0.0 --port ${PORT:-8000}"]
