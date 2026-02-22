# Stop‑Motion Capture Tool (Adaptive Edge Overlay)

A small desktop app to help with stop‑motion animation:

* Live preview from a USB camera (selected by index)
* Save captured frames to a chosen folder (`frame_0001.png`, `frame_0002.png`, …)
* Overlays **Canny edges from the previous captured frame** on the live preview
* Uses an **adaptive overlay** (inverts brightness at edge pixels) to stay visible across different backgrounds
* Adjustable overlay opacity
* Export captured frames to a video at a chosen FPS

---

## 1) Create a Conda environment

```bash
conda create -n stopmotion python=3.11 -y
conda activate stopmotion
```

> If you don’t have Conda, install Miniconda/Anaconda first.

---

## 2) Install dependencies

### Option A: Install via `requirements.txt`

```bash
pip install -r requirements.txt
```

### Option B: Install directly

```bash
pip install opencv-python PyQt6 numpy
```

---

## 3) Run the app

```bash
python stop_motion_app.py
```

---

## 4) How to use

1. **Choose Save Folder**

   * Click **Browse…** to select where frames will be saved.

2. **Select Camera**

   * Use the **Camera** dropdown.
   * If you have an internal webcam and a USB camera, the USB camera is often **index 1 or higher**.
   * Click **↻** to refresh the camera list.

3. **Capture frames**

   * Click **Capture** (or press **Space**).
   * Frames are saved as `frame_0001.png`, `frame_0002.png`, …

4. **Edge overlay**

   * The app overlays **edges from the previous captured frame** on top of the live preview.
   * The overlay uses an *adaptive inversion* so it remains visible without choosing a specific color.
   * Adjust visibility with the **Overlay** slider.

5. **Export video**

   * Click **Export Video**.
   * Enter your desired frame rate (FPS).
   * The output is written to `stopmotion_output.mp4` in the save folder.

---

## Keyboard shortcuts

* **Space**: Capture frame

---

## Files

* `stop_motion_app.py` — the application
* `requirements.txt` — Python dependencies
* `frames/` — default output folder if you don’t choose another

---

## Troubleshooting

### Camera doesn’t show up / wrong camera

* Try selecting a different camera index in the dropdown.
* Unplug/replug the USB camera, then hit **↻** refresh.
* Close other apps that might be using the camera.

### Video export plays too fast/slow

* The FPS you enter controls playback speed.
* Common stop‑motion frame rates: **10–15 fps** (often 12 fps).

### MP4 export issues

* Some systems have limited MP4 codec support via OpenCV.
* If MP4 fails on your machine, one workaround is exporting AVI (requires small code change) or using ffmpeg to re‑encode.

---
