# mac_webcam_snapshot

Simple one-shot webcam snapshot utility for macOS using OpenCV.

## Prerequisites

- Python 3.9+ recommended
- On macOS, grant Terminal (or your shell app) camera access in System Settings → Privacy & Security → Camera

## Setup

```bash
cd mac_webcam_snapshot
python3 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install opencv-python
```

## Run

```bash
# In this directory with the venv active
python3 snapshot.py
# -> Saves snapshot_<epoch>.jpg in the same directory
```

### Options

- `WEBCAM_INDEX` (default `0`): choose a different camera device index
- `OUTPUT` (default `snapshot_<epoch>.jpg`): set a custom output filename

Examples:

```bash
WEBCAM_INDEX=1 python3 snapshot.py
OUTPUT=my_pic.jpg python3 snapshot.py
```

If OpenCV cannot open the camera, try another index (0, 1, 2...) and ensure the app has permission to use the camera.


