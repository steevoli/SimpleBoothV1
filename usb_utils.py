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
from typing import Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

_USB_ROOT_ENV = os.environ.get("USB_ROOT", "")
USB_ROOT: Optional[Path] = Path(_USB_ROOT_ENV) if _USB_ROOT_ENV else None
SAVE_DIR: Optional[Path] = None


def _resolve_candidate(path: Path) -> Path:
    try:
        return path.expanduser().resolve(strict=False)
    except Exception:
        return path.expanduser()


def _ensure_compat_symlink(target: Optional[Path]) -> None:
    symlink_path = Path("/mnt/usb")
    try:
        if target is None:
            if symlink_path.is_symlink():
                symlink_path.unlink()
            return

        if symlink_path.exists():
            if symlink_path.is_symlink():
                try:
                    current_target = symlink_path.resolve(strict=False)
                except Exception:
                    current_target = None
                if current_target != target:
                    symlink_path.unlink()
                    symlink_path.symlink_to(target)
            else:
                # Un dossier réel existe déjà, ne pas le remplacer
                return
        else:
            symlink_path.parent.mkdir(parents=True, exist_ok=True)
            symlink_path.symlink_to(target)
    except PermissionError as exc:
        logger.debug("[USB] Impossible de gérer le lien symbolique %s: %s", symlink_path, exc)
    except OSError as exc:
        logger.debug("[USB] Erreur lors de la création du lien symbolique %s: %s", symlink_path, exc)


def _set_usb_paths(root: Optional[Path]) -> Tuple[Optional[Path], Optional[Path]]:
    global USB_ROOT, SAVE_DIR
    if root is None:
        USB_ROOT = None
        SAVE_DIR = None
        _ensure_compat_symlink(None)
        return USB_ROOT, SAVE_DIR

    resolved_root = _resolve_candidate(root)
    USB_ROOT = resolved_root
    save_dir = resolved_root / "sauvegardes"
    SAVE_DIR = save_dir
    try:
        save_dir.mkdir(parents=True, exist_ok=True)
    except FileNotFoundError:
        # Parent directory n'existe pas encore : laisser check_usb_health gérer
        pass
    except PermissionError as exc:
        logger.debug("[USB] Impossible de créer le dossier de sauvegarde %s: %s", save_dir, exc)
    except OSError as exc:
        logger.debug("[USB] Erreur lors de la création du dossier de sauvegarde %s: %s", save_dir, exc)
    _ensure_compat_symlink(USB_ROOT)
    return USB_ROOT, SAVE_DIR


def find_usb_root() -> Optional[Path]:
    """Detect the USB root directory using the configured environment or heuristics."""

    if _USB_ROOT_ENV:
        return _resolve_candidate(Path(_USB_ROOT_ENV))

    candidates: List[Path] = []
    user_name = os.environ.get("USER") or os.environ.get("USERNAME")
    if user_name:
        candidates.append(Path("/media") / user_name)
    candidates.extend([Path("/media"), Path("/run/media")])

    for base in candidates:
        try:
            entries = sorted(p for p in base.iterdir() if p.is_dir())
        except FileNotFoundError:
            continue
        except PermissionError as exc:
            logger.debug("[USB] Accès refusé à %s: %s", base, exc)
            continue
        for entry in entries:
            if not entry.exists():
                continue
            mount_entry = _find_mount_entry(entry)
            if mount_entry is None:
                continue
            if not os.access(entry, os.W_OK | os.X_OK):
                logger.debug("[USB] %s non accessible en écriture", entry)
                continue
            if _test_write_access(entry) is not None:
                logger.debug("[USB] Impossible d'écrire sur %s", entry)
                continue
            return _resolve_candidate(entry)

    return None


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
            "root": str(USB_ROOT) if USB_ROOT else None,
            "path": str(USB_ROOT) if USB_ROOT else None,
            "save_dir": str(SAVE_DIR) if SAVE_DIR else None,
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

    global USB_ROOT, SAVE_DIR

    if USB_ROOT is None:
        detected = find_usb_root()
        if detected is not None:
            _set_usb_paths(detected)
        else:
            return UsbHealth(
                mounted=False,
                writable=False,
                filesystem=None,
                free_bytes=None,
                detail="not_detected",
                message="Aucune clé USB détectée.",
            )

    assert USB_ROOT is not None
    root = USB_ROOT

    if not root.exists():
        return UsbHealth(
            mounted=False,
            writable=False,
            filesystem=None,
            free_bytes=None,
            detail="mount_point_missing",
            message=f"Le point de montage {root} est introuvable.",
        )

    if not root.is_dir():
        return UsbHealth(
            mounted=False,
            writable=False,
            filesystem=None,
            free_bytes=None,
            detail="not_a_directory",
            message=f"{root} n'est pas un dossier.",
        )

    entry = _find_mount_entry(root)
    if entry is None:
        return UsbHealth(
            mounted=False,
            writable=False,
            filesystem=None,
            free_bytes=None,
            detail="not_mounted",
            message=f"Aucun système de fichiers monté sur {root}.",
        )

    try:
        usage = shutil.disk_usage(root)
        free_bytes = usage.free
    except PermissionError as exc:
        return UsbHealth(
            mounted=True,
            writable=False,
            filesystem=entry.filesystem,
            free_bytes=None,
            detail="permission_denied",
            message=f"Permission refusée sur {root}: {exc}",
        )

    save_dir = (SAVE_DIR or (root / "sauvegardes")).resolve(strict=False)
    try:
        save_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        return UsbHealth(
            mounted=True,
            writable=False,
            filesystem=entry.filesystem,
            free_bytes=free_bytes,
            detail="permission_denied",
            message=f"Permission refusée pour créer {save_dir}: {exc}",
        )
    except OSError as exc:
        return UsbHealth(
            mounted=True,
            writable=False,
            filesystem=entry.filesystem,
            free_bytes=free_bytes,
            detail="io_error",
            message=f"Impossible de préparer {save_dir}: {exc}",
        )

    SAVE_DIR = save_dir

    writable = os.access(save_dir, os.W_OK | os.X_OK)
    detail = None
    message = None
    if not writable:
        detail = "permission_denied"
        message = "Droits insuffisants pour écrire sur la clé USB."
    elif test_write:
        error = _test_write_access(save_dir)
        if error is not None:
            writable = False
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
        writable=writable,
        filesystem=entry.filesystem,
        free_bytes=free_bytes,
        detail=detail,
        message=message,
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
    root = _require_usb_root()
    base_path = (base or root).resolve()
    if not _is_subpath(base_path, root):
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


def _require_usb_root() -> Path:
    global USB_ROOT
    if USB_ROOT is None:
        detected = find_usb_root()
        if detected is not None:
            _set_usb_paths(detected)
    if USB_ROOT is None:
        raise UsbUnavailableError("not_detected", "Clé USB non détectée.")
    return USB_ROOT


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_save_directory(subdir: Optional[str] = None) -> Path:
    root = _require_usb_root()
    base_dir = (SAVE_DIR or (root / "sauvegardes")).resolve(strict=False)
    if not _is_subpath(base_dir, root):
        raise UsbPathError("Le dossier de sauvegarde est hors de la clé USB")
    ensure_directory(base_dir)

    if subdir:
        relative_subdir = _ensure_relative_path(subdir)
        candidate = (base_dir / relative_subdir).resolve(strict=False)
        if not _is_subpath(candidate, root):
            raise UsbPathError("Sous-dossier hors de la clé USB")
        ensure_directory(candidate)
        return candidate

    return base_dir


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
        status_code = 507 if detail == "no_space" else 503
        raise UsbUnavailableError(detail, message, status_code=status_code)
    return health


def ensure_free_space(target_dir: Path, required_bytes: int) -> None:
    if required_bytes <= 0:
        return
    usage = shutil.disk_usage(target_dir)
    if usage.free < required_bytes:
        raise UsbUnavailableError("no_space", "Espace disque insuffisant sur la clé USB.", status_code=507)


def prepare_save_path(filename: str, subdir: Optional[str] = None) -> Path:
    validate_filename(filename)
    root = _require_usb_root().resolve(strict=False)
    target_dir = ensure_save_directory(subdir=subdir)
    destination = (target_dir / filename).resolve(strict=False)
    if not _is_subpath(destination, root):
        raise UsbPathError("Chemin de sauvegarde hors de la clé USB")
    return destination


def list_directory(relative_path: str = "") -> dict:
    ensure_usb_ready(for_writing=False)
    root = _require_usb_root()
    if relative_path:
        target = resolve_usb_path(relative_path)
    else:
        target = root
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
                "path": str(entry.relative_to(root)),
            }
        )
    return {
        "path": str(target.relative_to(root)) if target != root else "",
        "items": entries,
    }


def make_directory(relative_path: str) -> Path:
    ensure_usb_ready(for_writing=True)
    target = resolve_usb_path(relative_path)
    ensure_directory(target)
    return target


def save_content(filename: str, data: bytes, subdir: Optional[str] = None) -> Path:
    health = ensure_usb_ready(for_writing=True)
    destination = prepare_save_path(filename, subdir=subdir)

    data_size = len(data)
    if health.free_bytes is not None and health.free_bytes < data_size:
        raise UsbUnavailableError("no_space", "Espace disque insuffisant sur la clé USB.", status_code=507)

    ensure_free_space(destination.parent, data_size)

    with open(destination, "wb") as fh:
        fh.write(data)
    return destination


def pretty_print_health(health: UsbHealth) -> str:
    return json.dumps(health.to_dict(), indent=2, ensure_ascii=False)


_set_usb_paths(find_usb_root())

