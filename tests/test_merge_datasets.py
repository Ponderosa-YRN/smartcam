"""The dataset merge is a script, but a silent remap bug there wastes hours of GPU time.

These tests pin the three things that go wrong quietly: colliding class ids, colliding
filenames between datasets, and unlabelled images sneaking into training as background.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def make_set(root: Path, names: list[str], rows: dict[str, str | None]) -> None:
    (root / "images" / "train").mkdir(parents=True)
    (root / "labels" / "train").mkdir(parents=True)
    (root / "images" / "val").mkdir(parents=True)
    (root / "labels" / "val").mkdir(parents=True)
    (root / "data.yaml").write_text(yaml.safe_dump({"names": names}), encoding="utf-8")
    for stem, label in rows.items():
        (root / "images" / "train" / f"{stem}.jpg").write_bytes(b"x")
        if label is not None:
            (root / "labels" / "train" / f"{stem}.txt").write_text(label, encoding="utf-8")


def test_merge_remaps_ids_and_keeps_files_apart(tmp_path):
    make_set(tmp_path / "base", ["person", "bicycle"], {"00001": "0 0.5 0.5 0.1 0.1", "00002": "1 0.4 0.4 0.2 0.2"})
    make_set(tmp_path / "fire", ["fire", "smoke"], {"00001": "0 0.3 0.3 0.3 0.3", "00003": "1 0.6 0.6 0.2 0.2"})

    out = tmp_path / "merged"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "merge_yolo_datasets.py"), "--out", str(out),
         "--set", f"base={tmp_path / 'base'}", "--set", f"fire={tmp_path / 'fire'}"],
        check=True, capture_output=True,
    )

    names = yaml.safe_load((out / "data.yaml").read_text(encoding="utf-8"))["names"]
    assert names == ["person", "bicycle", "fire", "smoke"]

    labels = {p.name: p.read_text(encoding="utf-8").split()[0] for p in (out / "labels" / "train").iterdir()}
    # fire's class 0 must become 2, not overwrite base's person at 0
    assert labels["base__00001.txt"] == "0"
    assert labels["base__00002.txt"] == "1"
    assert labels["fire__00001.txt"] == "2"
    assert labels["fire__00003.txt"] == "3"

    # both datasets contain 00001.jpg; neither may clobber the other
    assert len(list((out / "images" / "train").iterdir())) == 4


def test_unlabelled_images_are_skipped(tmp_path):
    make_set(tmp_path / "base", ["person"], {"00001": "0 0.5 0.5 0.1 0.1".replace("0.", "0.")})
    make_set(tmp_path / "fire", ["fire"], {"00002": None})  # image, no label file

    out = tmp_path / "merged"
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "merge_yolo_datasets.py"), "--out", str(out),
         "--set", f"base={tmp_path / 'base'}", "--set", f"fire={tmp_path / 'fire'}"],
        check=True, capture_output=True,
    )

    stems = {p.stem for p in (out / "images" / "train").iterdir()}
    assert stems == {"base__00001"}, "an unlabelled image would teach the model that object is background"
