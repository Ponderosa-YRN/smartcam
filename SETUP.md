# SmartCam — Setup in VS Code

This is a self-contained copy of the SmartCam project. Keep it in its own
folder — it is fully independent of any other yolov8 project.

## 1. Open in VS Code

Open this folder in VS Code (File → Open Folder).

## 2. Create a virtual environment

Open the terminal in VS Code (Ctrl + `) and run:

    python -m venv .venv

If your machine already has torch + OpenCV installed (e.g. from another
project), reuse them to skip the big download:

    python -m venv --system-site-packages .venv

## 3. Install dependencies

    .venv\Scripts\python -m pip install --upgrade pip
    .venv\Scripts\python -m pip install -r requirements.txt

## 4. Run

    .venv\Scripts\python -m streamlit run app.py

Then open the printed URL (usually http://localhost:8501).

## 5. Demo clip (optional)

A demo clip is included at demo/demo.avi. To fetch a fresh one:

    .venv\Scripts\python scripts\download_demo.py

## Notes

- First run auto-downloads the YOLO weights (yolov8n.pt, ~6 MB).
- AI features (ANPR / face / ReID) download their models on first use and need
  their extra packages (easyocr, deepface, torchreid — all in requirements.txt).
- Configure everything from the dashboard → Settings (cameras, zones,
  detection, events, AI, security).

## Optional packages (if you skipped them)

    .venv\Scripts\python -m pip install easyocr        # license plates (ANPR)
    .venv\Scripts\python -m pip install deepface       # face recognition
    .venv\Scripts\python -m pip install torchreid      # cross-camera ReID
    .venv\Scripts\python -m pip install streamlit-drawable-canvas  # draw zones
