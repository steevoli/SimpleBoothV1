"""Utilitaires pour la gestion de la sauvegarde USB."""
from __future__ import annotations

import logging
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

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


def _iter_linux_mount_candidates() -> Iterable[Path]:
    bases = [Path("/media"), Path("/run/media")]
    for base in bases:
        if not base.exists():
            continue
        for first_level in base.iterdir():
            if not first_level.is_dir():
                continue
            # Certains systèmes montent directement à /media/USB
            if _is_valid_mount(first_level):
                yield first_level
            for second_level in first_level.iterdir():
                if second_level.is_dir():
                    yield second_level


def _iter_macos_mount_candidates() -> Iterable[Path]:
    base = Path("/Volumes")
    if base.exists():
        for child in base.iterdir():
            if child.is_dir():
                yield child


def _iter_windows_mount_candidates() -> Iterable[Path]:
    try:
        import ctypes

        drive_bits = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in (f"{chr(65 + i)}:" for i in range(26)):
            mask = 1 << (ord(letter[0]) - 65)
            if not drive_bits & mask:
                continue
            drive_type = ctypes.windll.kernel32.GetDriveTypeW(f"{letter}\\")
            # 2 = DRIVE_REMOVABLE
            if drive_type == 2:
                yield Path(f"{letter}\\")
    except Exception as exc:  # pragma: no cover - dépend du système
        logger.debug("[USB] Échec de détection Windows via ctypes: %s", exc)
        # Fallback simple: lettres E à Z
        for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
            path = Path(f"{letter}:/")
            if path.exists():
                yield path


def _is_valid_mount(path: Path) -> bool:
    try:
        if not path.exists() or not path.is_dir():
            return False
        # Éviter les montages système évidents
        lower = path.name.lower()
        if any(keyword in lower for keyword in ("system", "boot", "root", "efi")):
            return False
        # Vérifie que le chemin correspond à un point de montage réel quand possible
        if hasattr(os.path, "ismount") and os.path.ismount(path):
            return True
        # Sur Windows certains lecteurs ne sont pas considérés comme montés
        return True
    except Exception as exc:
        logger.debug("[USB] Chemin %s ignoré: %s", path, exc)
        return False


def get_usb_mount_point() -> Optional[Path]:
    """Retourne le point de montage de la première clé USB détectée."""

    logger.debug("[USB] Détection du point de montage USB...")
    candidates: Iterable[Path]

    if sys.platform.startswith("linux"):
        candidates = _iter_linux_mount_candidates()
    elif sys.platform.startswith("win"):
        candidates = _iter_windows_mount_candidates()
    elif sys.platform.startswith("darwin"):
        candidates = _iter_macos_mount_candidates()
    else:
        candidates = []

    for candidate in candidates:
        if _is_valid_mount(candidate):
            logger.info("[USB] Point de montage détecté: %s", candidate)
            return candidate

    logger.info("[USB] Aucune clé USB détectée")
    return None


def ensure_usb_folder_exists(subfolder: str = USB_DEFAULT_SUBFOLDER) -> Path:
    """S'assure que le dossier de sauvegarde existe sur la clé USB."""

    mount_point = get_usb_mount_point()
    if not mount_point:
        raise FileNotFoundError("Aucune clé USB détectée")

    destination = mount_point / subfolder
    try:
        destination.mkdir(parents=True, exist_ok=True)
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
    usage = shutil.disk_usage(destination)
    if usage.free < file_size:
        logger.error("[USB] Espace disque insuffisant: %s restant", usage.free)
        raise OSError("Espace disque insuffisant sur la clé USB")


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
