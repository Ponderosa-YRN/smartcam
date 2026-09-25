"""Download a small public sample clip for a real detection demo.

Default: OpenCV's vtest.avi (pedestrians in a parking lot, ~2 MB, Apache-2.0
sample data). Pass a custom URL to grab any other clip.
"""
from __future__ import annotations

import sys
from pathlib import Path

DEFAULT_URL = "https://raw.githubusercontent.com/opencv/opencv/master/samples/data/vtest.avi"


def main(url: str = DEFAULT_URL, out: str = "demo/demo.avi") -> None:
    import requests

    dest = Path(out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {url} ...")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r{100*done//total}% ({done}/{total} bytes)", end="")
        print()
    print(f"saved {dest}")


if __name__ == "__main__":
    main(*sys.argv[1:])
