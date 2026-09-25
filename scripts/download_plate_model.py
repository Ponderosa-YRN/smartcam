"""Download a YOLOv8 license-plate detection model for higher-accuracy ANPR.

The model is saved to models/license_plate_detector.pt, then referenced in
config.json via:  "alpr": { "plate_model": "models/license_plate_detector.pt" }

Usage:
    .venv\\Scripts\\python scripts\\download_plate_model.py --url <model-url>
    .venv\\Scripts\\python scripts\\download_plate_model.py   (prints guidance)

You can get a YOLOv8 license-plate model from:
  - Hugging Face (search "yolov8 license plate"), use the "resolve/main/<file>.pt" URL
  - Ultralytics Hub (https://hub.ultralytics.com)
  - Roboflow (export YOLOv8 and use the download URL)
"""
from __future__ import annotations

import argparse
from pathlib import Path


def download(url: str, out: Path) -> None:
    import requests

    out.parent.mkdir(parents=True, exist_ok=True)
    print("Downloading", url)
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        with open(out, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 20):
                f.write(chunk)
                done += len(chunk)
                if total:
                    print("\r%d%% (%d/%d bytes)" % (100 * done // total, done, total), end="")
        print()
    print("Saved", out)
    print('Add to config.json:  "alpr": { "plate_model": "%s", ... }' % out)


def main() -> None:
    ap = argparse.ArgumentParser(description="Download a YOLOv8 license-plate detection model")
    ap.add_argument("--url", default=None, help="direct .pt download URL")
    ap.add_argument("--out", default="models/license_plate_detector.pt")
    args = ap.parse_args()

    if not args.url:
        print("Pass --url to a YOLOv8 license-plate model (.pt). Sources:")
        print("  - Hugging Face:  https://huggingface.co/<user>/<repo>/resolve/main/model.pt")
        print("  - Ultralytics Hub: https://hub.ultralytics.com/models/<slug>")
        print("  - Roboflow: export YOLOv8 and use its download URL")
        return

    download(args.url, Path(args.out))


if __name__ == "__main__":
    main()
