# Fire / Smoke Model — Training Plan

Adding fire and smoke detection to a model that already recognises people and vehicles.

**Not a config change.** The class list comes from the model file (`detector.py:68`), so this means
producing a new model, not toggling a setting.

---

## 1. The shape of the result

One YOLOv8n model with **82 classes**: the 80 COCO classes unchanged (ids 0–79), plus
`fire` at 80 and `smoke` at 81.

Keeping COCO ids unchanged is deliberate — zone rules, `trigger_classes` and existing configs all
refer to classes by name, and a shifted id would silently break them.

---

## 2. Fine-tune, do not train from scratch

Start from `yolov8n.pt`, which already knows people and vehicles. Fine-tuning on a merged dataset
teaches the new classes while preserving the old ones. Training from zero on a merged set needs
far more data and time for no benefit at this scale.

---

## 3. Datasets

You need two, in YOLO format (`images/`, `labels/`, `data.yaml` with a `names` list).

| Source | Notes |
|---|---|
| **COCO** (people, vehicles, etc.) | Convert with `from ultralytics.data.converter import convert_coco` or use an existing YOLO-format mirror |
| **D-Fire** (Kaggle) | ~21k fire/smoke images, widely used in papers. Check the licence before commercial use |
| **Roboflow Universe — fire/smoke** | Many small sets; check each licence, they vary |
| **FASDD** | Larger, more varied fire/smoke imagery |

**Check the licence of every dataset.** "Free to download" is not "free to ship in a commercial
product". D-Fire in particular is research-oriented — read its terms.

Keep a **held-out** slice of the fire data that never enters training. You will need it to measure
honestly.

---

## 4. Merge

`scripts/merge_yolo_datasets.py` copies both sets into one, shifting class ids so nothing collides,
and writes a combined `data.yaml`:

```bash
python scripts/merge_yolo_datasets.py --out merged \
    --set base=/data/coco-yolo \
    --set fire=/data/fire-yolo
```

It skips images with no label file — an unlabelled fire image teaches the model that fire is
background, which is exactly backwards. Audit that count: if `fire/train` reports far fewer images
than you downloaded, your labels are not where the script expects them.

---

## 5. Train

Needs a GPU. **Kaggle's free T4 (30 h/week) is enough for a yolov8n fine-tune** — that is the
cheapest honest route. RunPod or Lambda if you want it done in one sitting.

```bash
yolo detect train \
    data=merged/data.yaml \
    model=yolov8n.pt \
    epochs=100 \
    imgsz=640 \
    batch=16 \
    patience=20 \
    device=0
```

100 epochs on ~25k images is a few hours on a T4. Watch `mAP50` per class — the fire class will lag
the COCO classes badly at first, which is expected.

---

## 6. Export and deploy

```bash
yolo export model=runs/detect/train/weights/best.pt format=onnx opset=12 simplify=True
```

Then:

1. Put the `.onnx` next to `yolov8n.onnx` in the repo and in the image
2. Set `detection.model` to its filename (Settings → Detection, or `config.json`)
3. Add `fire` and `smoke` to `detection.trigger_classes`

Step 3 is the one people forget: a class the model can see but that is not in `trigger_classes`
produces no events and therefore no alerts.

Restart the API so the pipeline reloads the model.

---

## 7. Evaluate before you show anyone

**Recall is the easy half. False positives are what kills this feature.**

| Test | Pass condition |
|---|---|
| Held-out fire/smoke set | Recall stated honestly per class, with the threshold you will ship |
| Ordinary hotel footage — sunsets, headlights, steam from a kettle, orange curtains, welding | **Fewer than one false positive per hour**, measured not guessed |
| Night footage with IR | No systematic false positives on IR bloom |
| False negatives | List what it misses: small distant flames, thin smoke, smoke behind glass |

A fire alarm that cries wolf is worse than none, because it teaches staff to ignore alerts. If the
false-positive rate is unacceptable, ship it as a **review-queue flag** — "possible fire at 14:32,
here is the frame" — rather than an alarm. That wording is also more defensible than claiming
detection.

---

## 8. Limits to state plainly

- **Smoke is harder than flame.** Flame is bright and high-contrast; smoke is grey, low-contrast,
  and often looks like an empty corridor. Expect much weaker smoke recall.
- **Small distant flames** in a wide hotel lobby shot may be a handful of pixels — below what
  yolov8n can see at 640 px without tiling.
- **This is not a certified fire detection system.** It is an awareness aid on top of whatever
  certified alarms the building already has. Never position it as a replacement, and say so in
  writing.
- **Inference cost.** The merged model is the same size as the current one, so no speed penalty —
  but a fire in frame does not change the frame rate.

---

## 9. Order of work

1. Confirm dataset licences — stop here if any is non-commercial
2. Convert both to YOLO format
3. Merge, audit the image counts
4. Fine-tune on a GPU
5. Export ONNX
6. Evaluate against §7, especially false positives
7. Only then: config, `trigger_classes`, restart
