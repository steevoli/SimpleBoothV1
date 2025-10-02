#!/usr/bin/env python3
"""Camera service exposing health and snapshot endpoints for the photobooth."""

from __future__ import annotations

import io
import logging
import threading
from contextlib import contextmanager
from datetime import datetime

from flask import Flask, Response, jsonify
from flask_cors import CORS

try:
    from picamera2 import Picamera2
except Exception as exc:  # pragma: no cover - dependency missing on CI
    Picamera2 = None  # type: ignore[assignment]
    PICAMERA_IMPORT_ERROR = exc
else:
    PICAMERA_IMPORT_ERROR = None

LOGGER = logging.getLogger("camera_service")
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:5000"}})

_CAMERA_LOCK = threading.Lock()


class CameraUnavailableError(RuntimeError):
    """Raised when the camera cannot be acquired."""


@contextmanager
def open_camera() -> Picamera2:
    if Picamera2 is None:
        raise CameraUnavailableError(
            "Picamera2 non disponible: installez python3-picamera2 et vérifiez les permissions"
        )

    if not _CAMERA_LOCK.acquire(timeout=4):
        raise CameraUnavailableError("Caméra occupée par un autre processus")

    camera = None
    try:
        camera = Picamera2()
        still_config = camera.create_still_configuration()
        camera.configure(still_config)
        camera.start()
        yield camera
    finally:
        if camera is not None:
            try:
                camera.stop()
            except Exception:  # pragma: no cover - best effort cleanup
                LOGGER.exception("Erreur lors de l'arrêt de la caméra")
            try:
                camera.close()
            except Exception:  # pragma: no cover
                LOGGER.exception("Erreur lors de la fermeture de la caméra")
        _CAMERA_LOCK.release()


def capture_jpeg_bytes() -> bytes:
    with open_camera() as camera:
        buffer = io.BytesIO()
        camera.capture_file(buffer, format="jpeg")
        return buffer.getvalue()


def check_camera_ready() -> tuple[bool, str]:
    if PICAMERA_IMPORT_ERROR is not None:
        return False, f"Impossible d'importer Picamera2: {PICAMERA_IMPORT_ERROR}"

    try:
        with open_camera():
            return True, "ready"
    except CameraUnavailableError as exc:
        return False, str(exc)
    except Exception as exc:  # pragma: no cover - defensive programming
        LOGGER.exception("Erreur lors du test caméra")
        return False, f"Erreur caméra: {exc}"


@app.route("/health", methods=["GET"])
def health() -> Response:
    ok, detail = check_camera_ready()
    status_code = 200 if ok else 503
    payload = {"ok": ok}
    if ok:
        payload["camera"] = detail
    else:
        payload["error"] = detail
    return jsonify(payload), status_code


@app.route("/snapshot", methods=["GET"])
def snapshot() -> Response:
    try:
        jpeg_bytes = capture_jpeg_bytes()
    except CameraUnavailableError as exc:
        LOGGER.warning("Caméra indisponible: %s", exc)
        return jsonify({"ok": False, "error": str(exc)}), 503
    except TimeoutError as exc:  # pragma: no cover - safeguard
        LOGGER.error("Timeout caméra: %s", exc)
        return jsonify({"ok": False, "error": "Capture expirée"}), 503
    except Exception as exc:  # pragma: no cover
        LOGGER.exception("Erreur lors de la capture")
        return jsonify({"ok": False, "error": str(exc)}), 503

    headers = {
        "Content-Type": "image/jpeg",
        "Content-Disposition": f"inline; filename=snapshot_{datetime.now():%Y%m%d_%H%M%S}.jpg",
        "Cache-Control": "no-store, max-age=0",
    }
    return Response(jpeg_bytes, headers=headers)


def main() -> None:
    app.run(host="0.0.0.0", port=8080, debug=False)


if __name__ == "__main__":
    main()
