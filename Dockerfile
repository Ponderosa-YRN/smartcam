# SmartCam backend (FastAPI + detection pipeline).
#
# Build:  docker build -t smartcam .
# Run:    docker run -p 8000:8000 -v smartcam_data:/app/data smartcam
# Fly:    fly launch --region lhr   (it builds this image)
#
# To run the Streamlit dashboard instead, override the CMD:
#   docker run ... smartcam python -m streamlit run app.py --server.port=8501 --server.headless=true --server.address=0.0.0.0
FROM python:3.11-slim

# System libraries OpenCV + video encoding need.
RUN apt-get update && apt-get install -y --no-install-recommends         libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 ffmpeg     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# CPU-only PyTorch first (much smaller than the CUDA build).
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Clips, thumbnails, and the database persist here (mount a volume).
VOLUME ["/app/data"]

ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "python run_api.py --host 0.0.0.0 --port ${PORT:-8000}"]
