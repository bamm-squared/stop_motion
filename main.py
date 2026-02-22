#!/usr/bin/env python3
"""
Stop-Motion Capture Tool (USB camera) with:
- Live preview
- Save folder selection
- Capture frames to PNG sequence
- Overlay of PREVIOUS captured frame's Canny edges on live preview
  using per-pixel inversion (robust visibility in any environment)
- Overlay opacity slider
- Mirror preview toggle
- Render Video export (MP4/AVI) with selectable FPS

Install:
  pip install opencv-python PyQt6 numpy

Run:
  python stop_motion_app.py
"""

from __future__ import annotations

import sys
import os
import glob
import cv2
import numpy as np

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import Qt


def list_available_cameras(max_index: int = 12) -> list[int]:
    """Probe camera indices 0..max_index-1 and return those that open."""
    available: list[int] = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(i)
        if cap is not None and cap.isOpened():
            available.append(i)
            cap.release()
    return available


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def next_frame_index(folder: str) -> int:
    """Return next N for frame_{N:04d}.png in folder."""
    existing = sorted(glob.glob(os.path.join(folder, "frame_*.png")))
    if not existing:
        return 1
    base = os.path.basename(existing[-1])
    try:
        num = int(base.replace("frame_", "").replace(".png", ""))
    except ValueError:
        return 1
    return num + 1


class VideoSource(QtCore.QObject):
    frame_ready = QtCore.pyqtSignal(np.ndarray)  # BGR frame

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._grab)

        self.cap: cv2.VideoCapture | None = None
        self.cam_index: int = 0

    def start(self, cam_index: int, fps: int = 30) -> bool:
        self.stop()
        self.cam_index = cam_index

        if os.name == "nt":
            self.cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(cam_index)

        if not (self.cap and self.cap.isOpened()):
            self.cap = None
            return False

        # Try a reasonable resolution (camera may ignore)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        interval_ms = max(1, int(1000 / max(1, fps)))
        self._timer.start(interval_ms)
        return True

    def stop(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    def _grab(self) -> None:
        if not self.cap:
            return
        ok, frame = self.cap.read()
        if ok and frame is not None:
            self.frame_ready.emit(frame)


class ImageView(QtWidgets.QLabel):
    """Simple image display label that keeps aspect ratio."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(640, 360)
        self.setStyleSheet("background:#111; color:#eee;")

    def set_cv_image(self, bgr: np.ndarray) -> None:
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w, _ = rgb.shape
        qimg = QtGui.QImage(rgb.data, w, h, 3 * w, QtGui.QImage.Format.Format_RGB888)
        pix = QtGui.QPixmap.fromImage(qimg)
        self.setPixmap(
            pix.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, e: QtGui.QResizeEvent) -> None:
        if self.pixmap():
            self.setPixmap(
                self.pixmap().scaled(
                    self.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        super().resizeEvent(e)


class StopMotionApp(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Stop-Motion Capture (Inverted Edge Overlay)")
        self.setMinimumSize(980, 700)

        # State
        self.save_folder = os.path.abspath(os.path.join(os.getcwd(), "frames"))
        ensure_dir(self.save_folder)

        self.prev_edges: np.ndarray | None = None  # uint8, 0/255
        self.overlay_opacity: float = 0.55
        self.mirror_preview: bool = False

        # Video
        self.video = VideoSource()
        self.video.frame_ready.connect(self.on_frame)

        # UI
        self._build_ui()
        self._populate_cameras()
        self._connect_signals()

        # Start camera (prefer first non-zero index if available)
        if self.camera_combo.count() > 0 and self.camera_combo.isEnabled():
            self.start_camera(int(self.camera_combo.currentData()))

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main = QtWidgets.QVBoxLayout(central)
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)

        # Top bar
        top = QtWidgets.QHBoxLayout()
        top.setSpacing(8)

        top.addWidget(QtWidgets.QLabel("Save to:"))
        self.folder_edit = QtWidgets.QLineEdit(self.save_folder)
        self.folder_btn = QtWidgets.QPushButton("Browse…")
        self.folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        top.addWidget(self.folder_edit, 1)
        top.addWidget(self.folder_btn)

        top.addSpacing(14)
        top.addWidget(QtWidgets.QLabel("Camera:"))
        self.camera_combo = QtWidgets.QComboBox()
        self.refresh_btn = QtWidgets.QPushButton("↻")
        self.refresh_btn.setToolTip("Refresh camera list")
        self.refresh_btn.setFixedWidth(34)
        top.addWidget(self.camera_combo)
        top.addWidget(self.refresh_btn)

        top.addSpacing(14)
        self.capture_btn = QtWidgets.QPushButton("● Capture (Space)")
        self.capture_btn.setStyleSheet("font-weight:600;")
        self.capture_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        top.addWidget(self.capture_btn)

        self.mirror_chk = QtWidgets.QCheckBox("Mirror preview")
        top.addWidget(self.mirror_chk)

        top.addStretch(1)
        main.addLayout(top)

        # Preview
        self.view = ImageView()
        main.addWidget(self.view, 1)

        # Bottom bar
        bottom = QtWidgets.QHBoxLayout()
        bottom.setSpacing(8)

        self.opacity_label = QtWidgets.QLabel(f"Overlay: {int(self.overlay_opacity * 100)}%")
        self.opacity_slider = QtWidgets.QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(int(self.overlay_opacity * 100))
        bottom.addWidget(self.opacity_label)
        bottom.addWidget(self.opacity_slider, 1)

        bottom.addSpacing(16)
        bottom.addWidget(QtWidgets.QLabel("FPS:"))
        self.fps_spin = QtWidgets.QDoubleSpinBox()
        self.fps_spin.setRange(1.0, 60.0)
        self.fps_spin.setDecimals(1)
        self.fps_spin.setSingleStep(1.0)
        self.fps_spin.setValue(12.0)
        self.fps_spin.setFixedWidth(80)
        bottom.addWidget(self.fps_spin)

        self.render_btn = QtWidgets.QPushButton("Render Video…")
        self.render_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        bottom.addWidget(self.render_btn)

        self.hint = QtWidgets.QLabel("Edges = previous capture (inverted overlay for visibility).")
        self.hint.setStyleSheet("color:#aaa;")
        bottom.addStretch(1)
        bottom.addWidget(self.hint)

        main.addLayout(bottom)

        # Status bar
        self.status = self.statusBar()
        self.status.showMessage("Ready. Choose a folder and press Capture to start.")

    def _connect_signals(self) -> None:
        self.folder_btn.clicked.connect(self.choose_folder)
        self.folder_edit.editingFinished.connect(self.on_folder_changed)

        self.refresh_btn.clicked.connect(self._populate_cameras)
        self.camera_combo.currentIndexChanged.connect(self.on_camera_changed)

        self.capture_btn.clicked.connect(self.capture_frame)
        self.mirror_chk.toggled.connect(self.on_mirror_toggled)

        self.opacity_slider.valueChanged.connect(self.on_opacity_changed)
        self.render_btn.clicked.connect(self.render_video)

    def _populate_cameras(self) -> None:
        self.camera_combo.blockSignals(True)
        self.camera_combo.clear()

        cams = list_available_cameras()
        if not cams:
            self.camera_combo.addItem("No cameras found", 0)
            self.camera_combo.setEnabled(False)
            self.camera_combo.blockSignals(False)
            return

        self.camera_combo.setEnabled(True)
        for idx in cams:
            self.camera_combo.addItem(f"Camera {idx}", idx)

        # Prefer the first non-zero camera (often USB) if present
        default_row = 0
        for i in range(self.camera_combo.count()):
            if int(self.camera_combo.itemData(i)) != 0:
                default_row = i
                break
        self.camera_combo.setCurrentIndex(default_row)

        self.camera_combo.blockSignals(False)

    def start_camera(self, cam_index: int) -> None:
        ok = self.video.start(cam_index)
        if not ok:
            QtWidgets.QMessageBox.warning(self, "Camera", f"Could not open camera index {cam_index}.")
            return
        self.status.showMessage(f"Camera {cam_index} started.")

    # ---------- UI handlers ----------
    def choose_folder(self) -> None:
        directory = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select folder to save frames", self.save_folder
        )
        if directory:
            self.save_folder = directory
            self.folder_edit.setText(directory)
            ensure_dir(directory)
            self.status.showMessage(f"Save folder: {directory}")

    def on_folder_changed(self) -> None:
        directory = self.folder_edit.text().strip()
        if directory:
            ensure_dir(directory)
            self.save_folder = directory

    def on_camera_changed(self, _row: int) -> None:
        if not self.camera_combo.isEnabled():
            return
        cam_index = int(self.camera_combo.currentData())
        self.start_camera(cam_index)

    def on_mirror_toggled(self, checked: bool) -> None:
        self.mirror_preview = checked

    def on_opacity_changed(self, value: int) -> None:
        self.overlay_opacity = float(value) / 100.0
        self.opacity_label.setText(f"Overlay: {value}%")

    # ---------- Frame pipeline ----------
    def on_frame(self, frame_bgr: np.ndarray) -> None:
        if self.mirror_preview:
            frame_bgr = cv2.flip(frame_bgr, 1)

        display = frame_bgr.copy()

        # Overlay previous edges using per-pixel inversion for visibility
        if self.prev_edges is not None:
            edges = self.prev_edges

            # Match size (nearest so we don't thicken/blur 1px edges)
            if edges.shape[:2] != display.shape[:2]:
                edges = cv2.resize(
                    edges, (display.shape[1], display.shape[0]), interpolation=cv2.INTER_NEAREST
                )

            mask = (edges == 255)  # 2D boolean
            mask3 = np.repeat(mask[:, :, None], 3, axis=2)

            inv = 255 - display
            alpha = float(np.clip(self.overlay_opacity, 0.0, 1.0))

            # Blend between original and inverted image
            blended = cv2.addWeighted(display, 1.0 - alpha, inv, alpha, 0)

            # Only apply on edge pixels
            display = np.where(mask3, blended, display)

        self.view.set_cv_image(display)

    def capture_frame(self) -> None:
        if not self.video.cap:
            QtWidgets.QMessageBox.warning(self, "Capture", "Camera not started.")
            return

        ok, frame = self.video.cap.read()
        if not ok or frame is None:
            QtWidgets.QMessageBox.warning(self, "Capture", "Failed to read from camera.")
            return

        if self.mirror_preview:
            frame = cv2.flip(frame, 1)

        ensure_dir(self.save_folder)
        idx = next_frame_index(self.save_folder)
        path = os.path.join(self.save_folder, f"frame_{idx:04d}.png")
        cv2.imwrite(path, frame)

        # Compute edges for NEXT overlay
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        self.prev_edges = cv2.Canny(gray, 100, 200)

        self.status.showMessage(f"Saved {os.path.basename(path)} → {self.save_folder}")

    # ---------- Render video ----------
    def render_video(self) -> None:
        folder = self.save_folder
        ensure_dir(folder)

        frames = sorted(glob.glob(os.path.join(folder, "frame_*.png")))
        if not frames:
            QtWidgets.QMessageBox.information(self, "Render Video", "No frames found in the selected folder.")
            return

        first = cv2.imread(frames[0])
        if first is None:
            QtWidgets.QMessageBox.warning(self, "Render Video", "Failed to read the first frame.")
            return

        height, width = first.shape[:2]

        default_name = os.path.join(folder, "animation.mp4")
        out_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export video",
            default_name,
            "MP4 Video (*.mp4);;AVI Video (*.avi)"
        )
        if not out_path:
            return

        ext = os.path.splitext(out_path)[1].lower()
        fourcc = cv2.VideoWriter_fourcc(*("XVID" if ext == ".avi" else "mp4v"))

        fps = float(self.fps_spin.value())
        writer = cv2.VideoWriter(out_path, fourcc, fps, (width, height))
        if not writer.isOpened():
            QtWidgets.QMessageBox.critical(
                self,
                "Render Video",
                "Could not open the video writer. Try AVI, or a different folder/filename."
            )
            return

        written = 0
        for f in frames:
            img = cv2.imread(f)
            if img is None:
                continue
            if img.shape[:2] != (height, width):
                img = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)
            writer.write(img)
            written += 1

        writer.release()
        self.status.showMessage(f"Rendered {written} frames → {out_path} at {fps:.1f} fps")
        QtWidgets.QMessageBox.information(
            self,
            "Render Video",
            f"Done!\n\nSaved {written} frames to:\n{out_path}\n\nFPS: {fps:.1f}"
        )

    # ---------- Keyboard shortcuts ----------
    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space:
            self.capture_frame()
            event.accept()
            return
        if event.key() == Qt.Key.Key_S:
            self.choose_folder()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Q, Qt.Key.Key_Escape):
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)

    def closeEvent(self, e: QtGui.QCloseEvent) -> None:
        try:
            self.video.stop()
        finally:
            super().closeEvent(e)


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    w = StopMotionApp()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
