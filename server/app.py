#!/usr/bin/env python3
"""Serveur caméra SimpleBooth plan B.

Expose un flux MJPEG compatible Pi Camera (libcamera/picamera2) avec bascule
USB et une route de santé détaillée.
"""
from __future__ import annotations

import glob
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime
from typing import Deque, Optional

import cv2
from flask import Flask, Response, jsonify

try:
    from picamera2 import Picamera2  # type: ignore

    PICAMERA2_AVAILABLE = True
except Exception:  # pragma: no cover - dépend de l'environnement Raspberry Pi
    Picamera2 = None  # type: ignore
    PICAMERA2_AVAILABLE = False

LOG_FORMAT = "[%(levelname)s] %(asctime)s :: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("camera-server")

app = Flask(__name__)

_frame_lock = threading.Lock()
_last_frame_ts: Optional[float] = None
_last_backend: Optional[str] = None
_last_error: Optional[str] = None
_recent_errors: Deque[str] = deque(maxlen=10)

JPEG_PARAMS = [int(cv2.IMWRITE_JPEG_QUALITY), 85]


def _update_last_frame(timestamp: float, backend: str) -> None:
    global _last_frame_ts, _last_backend
    with _frame_lock:
        _last_frame_ts = timestamp
        _last_backend = backend


def _push_error(error: Exception | str) -> None:
    global _last_error
    message = str(error)
    _last_error = message
    stamp = datetime.utcnow().isoformat()
    entry = f"{stamp}Z :: {message}"
    _recent_errors.append(entry)
    logger.error("%s", entry)


def _open_picamera() -> Optional[Picamera2]:
    if not PICAMERA2_AVAILABLE:
        return None
    logger.info("[CAMERA] Initialisation Picamera2 ...")
    picam2 = Picamera2()
    config = picam2.create_video_configuration(
        main={"size": (1280, 720)},
        controls={"FrameDurationLimits": (33333, 33333)},
    )
    picam2.configure(config)
    picam2.start()
    logger.info("[CAMERA] Picamera2 démarrée")
    return picam2


def _yield_picamera_frames(picam2: Picamera2):
    global _last_frame_ts
    while True:
        frame = picam2.capture_array()
        if frame is None:
            raise RuntimeError("Frame Picamera2 vide")
        ret, jpeg = cv2.imencode(".jpg", frame, JPEG_PARAMS)
        if not ret:
            raise RuntimeError("Encodage JPEG Picamera2 échoué")
        ts = time.time()
        _update_last_frame(ts, "picamera2")
        yield jpeg.tobytes()


def _open_usb_camera(index: int = 0) -> cv2.VideoCapture:
    logger.info("[CAMERA] Tentative d'ouverture webcam USB index=%s", index)
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError("Aucune caméra USB disponible (index 0).")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 25)
    logger.info("[CAMERA] Webcam USB démarrée")
    return cap


def _yield_usb_frames(cap: cv2.VideoCapture):
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            raise RuntimeError("Lecture webcam USB impossible.")
        ret, jpeg = cv2.imencode(".jpg", frame, JPEG_PARAMS)
        if not ret:
            raise RuntimeError("Encodage JPEG webcam USB échoué")
        ts = time.time()
        _update_last_frame(ts, "usb")
        yield jpeg.tobytes()


@app.get("/camera/stream")
def stream() -> Response:
    """Flux MJPEG multi-source."""
    def generate():
        picam2 = None
        usb_cap = None
        try:
            if PICAMERA2_AVAILABLE:
                try:
                    picam2 = _open_picamera()
                    for jpeg in _yield_picamera_frames(picam2):
                        yield (
                            b"--frame\r\n"
                            b"Content-Type: image/jpeg\r\n\r\n"
                            + jpeg
                            + b"\r\n"
                        )
                except Exception as err:
                    _push_error(f"Pi Camera indisponible: {err}")
                    if picam2 is not None:
                        try:
                            picam2.stop()
                        except Exception:
                            pass
                        try:
                            picam2.close()
                        except Exception:
                            pass
                        picam2 = None
                    logger.info("[CAMERA] Bascule sur webcam USB")

            usb_cap = _open_usb_camera()
            for jpeg in _yield_usb_frames(usb_cap):
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n"
                    + jpeg
                    + b"\r\n"
                )
        except Exception as err:
            _push_error(err)
            raise
        finally:
            if picam2 is not None:
                try:
                    picam2.stop()
                except Exception:
                    pass
                try:
                    picam2.close()
                except Exception:
                    pass
            if usb_cap is not None:
                usb_cap.release()

    response = Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


@app.get("/camera/health")
def health() -> Response:
    import getpass
    import grp

    user = getpass.getuser()
    video_group_ok = False
    try:
        video_grp = grp.getgrnam("video")
        if user in video_grp.gr_mem or os.getgid() == video_grp.gr_gid:
            video_group_ok = True
    except KeyError:
        video_group_ok = False
    except Exception as err:  # pragma: no cover
        _push_error(f"Inspection groupe video impossible: {err}")

    if os.geteuid() == 0:
        video_group_ok = True

    with _frame_lock:
        last_ts = _last_frame_ts
        backend = _last_backend
        last_error = _last_error

    payload = {
        "has_picamera2": PICAMERA2_AVAILABLE,
        "video_group_ok": video_group_ok,
        "dev_video": sorted(glob.glob("/dev/video*")),
        "last_frame_ts": last_ts,
        "last_frame_iso": datetime.utcfromtimestamp(last_ts).isoformat() + "Z" if last_ts else None,
        "last_backend": backend,
        "last_error": last_error,
        "recent_errors": list(_recent_errors),
        "uptime_seconds": time.time() - psutil.boot_time() if _psutil_available() else None,
    }

    response = jsonify(payload)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


def _psutil_available() -> bool:
    try:
        import psutil  # type: ignore

        globals()["psutil"] = psutil
        return True
    except Exception:
        return False


@app.after_request
def add_cors_headers(response: Response) -> Response:  # pragma: no cover - simple entête
    response.headers.setdefault("Access-Control-Allow-Origin", "*")
    response.headers.setdefault("Access-Control-Allow-Headers", "Content-Type")
    response.headers.setdefault("Access-Control-Allow-Methods", "GET, OPTIONS")
    return response


if __name__ == "__main__":
    logger.info("Serveur caméra en écoute sur 0.0.0.0:8080")
    app.run(host="0.0.0.0", port=8080, threaded=True)
