#!/usr/bin/env python3
"""Merge YOLO-format datasets into one, remapping class ids.

Why this exists: fire/smoke models ship as their own 2-3 class datasets, and the
product needs one model that still recognises people and vehicles. Training a
merged model means one dataset with one contiguous class list, so the person class
must stay at id 0 and fire must not collide with an existing class id.

    python scripts/merge_yolo_datasets.py --out merged \
        --set base=/data/coco-yolo \
        --set fire=/data/fire-yolo

Each source is a YOLO dataset:

    <root>/data.yaml          names: [person, bicycle, ...]
    <root>/images/train/*.jpg
    <root>/labels/train/*.txt

Class ids from each source are shifted by the running total of classes already
added, so nothing collides. Files are copied (not moved) and prefixed with the
source name, because two datasets both contain 00001.jpg.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import yaml

SPLITS = ("train", "val")
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def load_names(root: Path) -> list[str]:
    data = yaml.safe_load((root / "data.yaml").read_text(encoding="utf-8"))
    names = data.get("names")
    if isinstance(names, dict):  # some exports use {0: 'person', ...}
        names = [names[k] for k in sorted(names)]
    if not isinstance(names, list):
        raise SystemExit(f"{root}/data.yaml has no usable 'names' list")
    return [str(n) for n in names]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="output dataset directory")
    ap.add_argument("--set", action="append", required=True, metavar="NAME=ROOT")
    args = ap.parse_args()

    sources = []
    for spec in args.set:
        name, _, root = spec.partition("=")
        if not root:
            raise SystemExit(f"--set needs NAME=ROOT, got {spec!r}")
        path = Path(root)
        if not (path / "data.yaml").exists():
            raise SystemExit(f"{path} has no data.yaml")
        sources.append((name, path, load_names(path)))

    out = Path(args.out)
    combined: list[str] = []
    offsets: dict[str, int] = {}
    for name, path, names in sources:
        offsets[name] = len(combined)
        combined.extend(names)
        print(f"{name:10s} offset {offsets[name]:3d}  {len(names)} classes")

    for split in SPLITS:
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)

    total = 0
    for name, root, names in sources:
        shift = offsets[name]
        for split in SPLITS:
            img_dir = root / "images" / split
            lbl_dir = root / "labels" / split
            if not img_dir.exists():
                print(f"  {name}: no images/{split}, skipped")
                continue
            copied = 0
            for img in img_dir.iterdir():
                if img.suffix.lower() not in IMAGE_EXTS:
                    continue
                stem = f"{name}__{img.stem}"
                label = lbl_dir / (img.stem + ".txt")
                if not label.exists():
                    continue  # an unlabelled image teaches the model nothing useful
                lines = []
                for row in label.read_text(encoding="utf-8").splitlines():
                    parts = row.split()
                    if len(parts) != 5:
                        continue
                    cls = int(parts[0])
                    if cls >= len(names):
                        continue
                    lines.append(" ".join([str(cls + shift)] + parts[1:]))
                if not lines:
                    continue
                shutil.copy2(img, out / "images" / split / (stem + img.suffix))
                (out / "labels" / split / (stem + ".txt")).write_text("\n".join(lines) + "\n", encoding="utf-8")
                copied += 1
            print(f"  {name}/{split}: {copied} images")
            total += copied

    (out / "data.yaml").write_text(
        yaml.safe_dump(
            {
                "path": str(out.resolve()),
                "train": "images/train",
                "val": "images/val",
                "names": combined,
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    added = [f"{i}={n}" for i, n in enumerate(combined) if i >= 80]
    print(f"\n{total} images, {len(combined)} classes -> {out}/data.yaml")
    print("Classes beyond COCO: " + (", ".join(added) if added else "none"))


if __name__ == "__main__":
    main()
