"""Utilities for managing the USB storage mount used by the photobooth."""
from __future__ import annotations

import errno
import json
import logging
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

logger = logging.getLogger(__name__)

USB_ROOT = Path(os.environ.get("USB_ROOT", "/mnt/usb")).resolve()
SAVE_DIR = Path(os.environ.get("USB_SAVE_DIR", str(USB_ROOT / "sauvegardes"))).resolve()


class UsbPathError(ValueError):
    """Raised when a requested path would escape from the USB root."""

    def __init__(self, message: str = "Chemin USB invalide") -> None:
        super().__init__(message)


class UsbUnavailableError(RuntimeError):
    """Raised when the USB mount cannot satisfy the requested operation."""

    def __init__(self, code: str, message: str, status_code: int = 503) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass
class UsbHealth:
    mounted: bool
    writable: bool
    filesystem: Optional[str]
    free_bytes: Optional[int]
    detail: Optional[str] = None
    message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "mounted": self.mounted,
            "writable": self.writable,
            "filesystem": self.filesystem,
            "free_bytes": self.free_bytes,
            "detail": self.detail,
            "message": self.message,
            "root": str(USB_ROOT),
            "save_dir": str(SAVE_DIR),
        }


@dataclass
class MountEntry:
    device: str
    mount_point: Path
    filesystem: str


def _decode_mount_value(value: str) -> str:
    return value.replace("\\040", " ")


def _iter_mounts() -> Iterable[MountEntry]:
    try:
        with open("/proc/mounts", "r", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 3:
                    continue
                device = _decode_mount_value(parts[0])
                mount_point = Path(_decode_mount_value(parts[1]))
                fs_type = parts[2]
                yield MountEntry(device=device, mount_point=mount_point, filesystem=fs_type)
    except FileNotFoundError:
        # macOS or systems without /proc
        try:
            output = subprocess.check_output(["mount"], text=True)
        except Exception as exc:  # pragma: no cover - depends on system
            logger.debug("[USB] Impossible de lire la table de montages: %s", exc)
            return
        for line in output.splitlines():
            parts = line.split(" on ")
            if len(parts) < 2:
                continue
            device = parts[0].strip()
            rest = parts[1].split(" type ")
            if len(rest) < 2:
                continue
            mount_point = Path(rest[0].strip())
            fs_type = rest[1].split()[0]
            yield MountEntry(device=device, mount_point=mount_point, filesystem=fs_type)


def _find_mount_entry(path: Path) -> Optional[MountEntry]:
    for entry in _iter_mounts():
        if entry.mount_point == path:
            return entry
    return None


def _test_write_access(directory: Path) -> Optional[OSError]:
    probe_name = directory / f".usb_write_test_{uuid.uuid4().hex}"
    try:
        with open(probe_name, "wb") as fh:
            fh.write(b"test")
        probe_name.unlink(missing_ok=True)
        return None
    except OSError as exc:
        try:
            probe_name.unlink(missing_ok=True)
        except OSError:
            pass
        return exc


def check_usb_health(test_write: bool = False) -> UsbHealth:
    """Return the health information for the configured USB mount."""

    if not USB_ROOT.exists():
        return UsbHealth(
            mounted=False,
            writable=False,
            filesystem=None,
            free_bytes=None,
            detail="mount_point_missing",
            message=f"Le point de montage {USB_ROOT} est introuvable.",
        )

    if not USB_ROOT.is_dir():
        return UsbHealth(
            mounted=False,
            writable=False,
            filesystem=None,
            free_bytes=None,
            detail="not_a_directory",
            message=f"{USB_ROOT} n'est pas un dossier.",
        )

    entry = _find_mount_entry(USB_ROOT)
    if entry is None:
        return UsbHealth(
            mounted=False,
            writable=False,
            filesystem=None,
            free_bytes=None,
            detail="not_mounted",
            message=f"Aucun système de fichiers monté sur {USB_ROOT}.",
        )

    try:
        usage = shutil.disk_usage(USB_ROOT)
        free_bytes = usage.free
    except PermissionError as exc:
        return UsbHealth(
            mounted=True,
            writable=False,
            filesystem=entry.filesystem,
            free_bytes=None,
            detail="permission_denied",
            message=f"Permission refusée sur {USB_ROOT}: {exc}",
        )

    if not os.access(USB_ROOT, os.W_OK | os.X_OK):
        return UsbHealth(
            mounted=True,
            writable=False,
            filesystem=entry.filesystem,
            free_bytes=free_bytes,
            detail="permission_denied",
            message="Droits insuffisants pour écrire sur la clé USB.",
        )

    if test_write:
        error = _test_write_access(USB_ROOT)
        if error is not None:
            detail = "io_error"
            message = str(error)
            if isinstance(error, PermissionError):
                detail = "permission_denied"
                message = "Droits insuffisants pour écrire sur la clé USB."
            elif error.errno == errno.EROFS:
                detail = "read_only"
                message = "La clé USB est montée en lecture seule."
            elif error.errno == errno.ENOSPC:
                detail = "no_space"
                message = "Espace disque insuffisant sur la clé USB."
            return UsbHealth(
                mounted=True,
                writable=False,
                filesystem=entry.filesystem,
                free_bytes=free_bytes,
                detail=detail,
                message=message,
            )

    return UsbHealth(
        mounted=True,
        writable=True,
        filesystem=entry.filesystem,
        free_bytes=free_bytes,
    )


def _ensure_relative_path(relative_path: str) -> Path:
    if relative_path is None:
        raise UsbPathError("Chemin manquant")
    relative_path = relative_path.strip()
    if not relative_path:
        raise UsbPathError("Chemin vide")
    if relative_path.startswith("/"):
        raise UsbPathError("Les chemins absolus sont interdits")

    path_obj = Path(relative_path)
    for part in path_obj.parts:
        if part in ("", ".", ".."):
            raise UsbPathError("Navigation hors du dossier USB interdite")
        if "\x00" in part:
            raise UsbPathError("Caractère nul interdit dans les chemins")
    return path_obj


def resolve_usb_path(relative_path: str, base: Optional[Path] = None) -> Path:
    base_path = (base or USB_ROOT).resolve()
    if not _is_subpath(base_path, USB_ROOT):
        raise UsbPathError("Base en dehors de la clé USB")

    path_obj = _ensure_relative_path(relative_path)
    candidate = (base_path / path_obj).resolve()
    if not _is_subpath(candidate, base_path):
        raise UsbPathError("Chemin hors de la clé USB")
    return candidate


def _is_subpath(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_save_directory(subdir: Optional[str] = None) -> Path:
    destination = SAVE_DIR
    ensure_directory(destination)
    if subdir:
        destination = resolve_usb_path(subdir, base=destination)
        ensure_directory(destination)
    return destination


def validate_filename(filename: str) -> str:
    if not filename:
        raise UsbPathError("Nom de fichier manquant")
    filename = filename.strip()
    if not filename:
        raise UsbPathError("Nom de fichier vide")
    if any(sep and sep in filename for sep in (os.sep, os.altsep) if sep):
        raise UsbPathError("Le nom de fichier ne doit pas contenir de séparateur")
    if filename in (".", ".."):
        raise UsbPathError("Nom de fichier invalide")
    if "\x00" in filename:
        raise UsbPathError("Caractère nul interdit")
    return filename


def ensure_usb_ready(for_writing: bool = False) -> UsbHealth:
    health = check_usb_health(test_write=for_writing)
    if not health.mounted:
        raise UsbUnavailableError(health.detail or "not_mounted", health.message or "Clé USB non montée.")
    if for_writing and not health.writable:
        detail = health.detail or "read_only"
        message = health.message or "Clé USB non disponible en écriture."
        raise UsbUnavailableError(detail, message)
    return health


def ensure_free_space(target_dir: Path, required_bytes: int) -> None:
    if required_bytes <= 0:
        return
    usage = shutil.disk_usage(target_dir)
    if usage.free < required_bytes:
        raise UsbUnavailableError("no_space", "Espace disque insuffisant sur la clé USB.", status_code=507)


def list_directory(relative_path: str = "") -> dict:
    ensure_usb_ready(for_writing=False)
    if relative_path:
        target = resolve_usb_path(relative_path)
    else:
        target = USB_ROOT
    if not target.exists():
        raise FileNotFoundError("Le dossier demandé n'existe pas sur la clé USB")
    if not target.is_dir():
        raise NotADirectoryError("Le chemin demandé n'est pas un dossier")

    entries: List[dict] = []
    for entry in sorted(target.iterdir(), key=lambda p: p.name.lower()):
        try:
            stat_result = entry.stat()
        except OSError as exc:
            logger.warning("[USB] Impossible de lire %s: %s", entry, exc)
            continue
        entry_type = "directory" if entry.is_dir() else "file"
        entries.append(
            {
                "name": entry.name,
                "type": entry_type,
                "size": stat_result.st_size,
                "mtime": stat_result.st_mtime,
                "path": str(entry.relative_to(USB_ROOT)),
            }
        )
    return {"path": str(target.relative_to(USB_ROOT)) if target != USB_ROOT else "", "items": entries}


def make_directory(relative_path: str) -> Path:
    ensure_usb_ready(for_writing=True)
    target = resolve_usb_path(relative_path)
    ensure_directory(target)
    return target


def save_content(filename: str, data: bytes, subdir: Optional[str] = None) -> Path:
    validate_filename(filename)
    ensure_usb_ready(for_writing=True)
    target_dir = ensure_save_directory(subdir=subdir)
    ensure_free_space(target_dir, len(data))
    destination = target_dir / filename
    with open(destination, "wb") as fh:
        fh.write(data)
    return destination


def pretty_print_health(health: UsbHealth) -> str:
    return json.dumps(health.to_dict(), indent=2, ensure_ascii=False)

