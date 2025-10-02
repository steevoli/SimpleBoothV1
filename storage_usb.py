"""Utilitaires pour la gestion de la sauvegarde USB."""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from usb_utils import (
    USB_ROOT,
    UsbPathError,
    UsbUnavailableError,
    check_usb_health,
    ensure_directory,
    ensure_free_space,
    ensure_usb_ready,
    resolve_usb_path,
)

logger = logging.getLogger(__name__)

USB_DEFAULT_SUBFOLDER = "SimpleBooth"


@dataclass
class PhotoMeta:
    """Métadonnées minimalistes pour une photo stockée sur USB."""

    name: str
    path: str
    size: int
    mtime: float

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "mtime": self.mtime,
        }


def get_usb_mount_point() -> Optional[Path]:
    """Retourne le point de montage configuré si disponible."""

    health = check_usb_health()
    if health.mounted and USB_ROOT is not None:
        return USB_ROOT
    logger.info("[USB] Point de montage USB indisponible: %s", health.message)
    return None


def _rethrow_unavailable(exc: UsbUnavailableError) -> None:
    if exc.code in {"not_mounted", "mount_point_missing", "not_a_directory"}:
        raise FileNotFoundError(str(exc)) from exc
    if exc.code in {"permission_denied", "read_only"}:
        raise PermissionError(str(exc)) from exc
    raise OSError(str(exc)) from exc


def ensure_usb_folder_exists(subfolder: str = USB_DEFAULT_SUBFOLDER) -> Path:
    """S'assure que le dossier de sauvegarde existe sur la clé USB."""

    try:
        ensure_usb_ready(for_writing=True)
    except UsbUnavailableError as exc:
        _rethrow_unavailable(exc)

    if subfolder:
        try:
            destination = resolve_usb_path(subfolder)
        except UsbUnavailableError as exc:
            _rethrow_unavailable(exc)
        except UsbPathError as exc:
            raise OSError(str(exc)) from exc
        except Exception as exc:  # pragma: no cover - validation
            raise OSError(str(exc)) from exc
    else:
        if USB_ROOT is None:
            raise OSError("Clé USB non détectée")
        destination = USB_ROOT

    try:
        ensure_directory(destination)
    except PermissionError as exc:
        logger.error("[USB] Permission refusée pour créer %s: %s", destination, exc)
        raise
    except OSError as exc:
        logger.error("[USB] Impossible de créer %s: %s", destination, exc)
        raise

    return destination


def _generate_timestamp_name(original: Path, dest_name_timestamped: bool) -> str:
    if not dest_name_timestamped:
        return original.name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = original.suffix or ".jpg"
    return f"{timestamp}{suffix}".replace(" ", "_")


def _check_free_space(destination: Path, file_size: int) -> None:
    try:
        ensure_free_space(destination, file_size)
    except UsbUnavailableError as exc:
        if exc.code == "no_space":
            logger.error("[USB] Espace disque insuffisant sur %s", destination)
            raise OSError(str(exc)) from exc
        raise


def _build_unique_path(destination_folder: Path, filename: str) -> Path:
    base_path = destination_folder / filename
    candidate = base_path
    counter = 1
    while candidate.exists():
        candidate = destination_folder / f"{base_path.stem}_{counter}{base_path.suffix}"
        counter += 1
    return candidate


def save_photo_to_usb(image_source, dest_name_timestamped: bool = True, subfolder: str = USB_DEFAULT_SUBFOLDER) -> Path:
    """Sauvegarde une photo (chemin ou bytes) sur la clé USB et retourne le chemin créé."""

    destination_folder = ensure_usb_folder_exists(subfolder=subfolder)

    if isinstance(image_source, (str, Path)):
        source_path = Path(image_source)
        if not source_path.exists():
            raise FileNotFoundError(f"Fichier introuvable: {source_path}")
        file_size = source_path.stat().st_size
        _check_free_space(destination_folder, file_size)
        dest_name = _generate_timestamp_name(source_path, dest_name_timestamped)
        dest_path = _build_unique_path(destination_folder, dest_name)
        shutil.copy2(source_path, dest_path)
        logger.info("[USB] Photo copiée sur USB: %s", dest_path)
        return dest_path

    if isinstance(image_source, (bytes, bytearray)):
        data = bytes(image_source)
        file_size = len(data)
        _check_free_space(destination_folder, file_size)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest_path = _build_unique_path(destination_folder, f"{timestamp}.jpg")
        with open(dest_path, "wb") as output:
            output.write(data)
        logger.info("[USB] Photo sauvegardée depuis bytes: %s", dest_path)
        return dest_path

    raise TypeError("image_source doit être un chemin ou des octets")


def list_usb_photos(subfolder: str = USB_DEFAULT_SUBFOLDER) -> List[dict]:
    """Liste les photos présentes sur la clé USB."""

    folder = ensure_usb_folder_exists(subfolder=subfolder)
    photos: List[PhotoMeta] = []
    for file in sorted(folder.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True):
        if not file.is_file():
            continue
        stats = file.stat()
        photos.append(PhotoMeta(
            name=file.name,
            path=str(file),
            size=stats.st_size,
            mtime=stats.st_mtime,
        ))
    logger.info("[USB] %d photos détectées sur la clé", len(photos))
    return [photo.to_dict() for photo in photos]


def delete_usb_photo(path: str, subfolder: str = USB_DEFAULT_SUBFOLDER) -> bool:
    """Supprime une photo du dossier USB."""

    folder = ensure_usb_folder_exists(subfolder=subfolder)
    target = folder / Path(path).name
    if not target.exists():
        logger.warning("[USB] Photo introuvable pour suppression: %s", target)
        return False
    try:
        target.unlink()
        logger.info("[USB] Photo supprimée: %s", target)
        return True
    except PermissionError as exc:
        logger.error("[USB] Permission refusée pour supprimer %s: %s", target, exc)
        raise
    except OSError as exc:
        logger.error("[USB] Erreur lors de la suppression de %s: %s", target, exc)
        raise
