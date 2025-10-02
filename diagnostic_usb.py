#!/usr/bin/env python3
"""Diagnostic léger pour vérifier la disponibilité de la clé USB."""

from __future__ import annotations

import sys
from pathlib import Path

from usb_utils import SAVE_DIR, USB_ROOT, check_usb_health, ensure_save_directory, find_usb_root


def describe_path(path: Path | None) -> str:
    if path is None:
        return "(aucun)"
    return str(path)


def test_write(save_dir: Path) -> tuple[bool, str]:
    probe = save_dir / ".__test__"
    try:
        save_dir.mkdir(parents=True, exist_ok=True)
        with open(probe, "wb") as fh:
            fh.write(b"diagnostic")
        probe.unlink(missing_ok=True)
        return True, "succès"
    except OSError as exc:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
        return False, f"échec ({exc})"


def main() -> int:
    detected = find_usb_root()
    print("=== Diagnostic USB ===")
    print(f"Chemin détecté : {describe_path(detected)}")
    print(f"Chemin courant : {describe_path(USB_ROOT)}")

    health = check_usb_health(test_write=True)
    print("\n--- État ---")
    print(f"Monté          : {health.mounted}")
    print(f"Écriture OK    : {health.writable}")
    print(f"Système de fichiers : {health.filesystem or '(inconnu)'}")
    print(f"Espace libre   : {health.free_bytes if health.free_bytes is not None else '(inconnu)'}")
    if health.message:
        print(f"Message        : {health.message}")
    if health.detail:
        print(f"Code détail    : {health.detail}")

    save_dir = SAVE_DIR or (detected / "sauvegardes" if detected else None)
    print(f"\nDossier sauvegarde : {describe_path(save_dir)}")

    if health.mounted and health.writable and save_dir is not None:
        ensure_save_directory()
        ok, message = test_write(save_dir)
        print(f"Test écriture  : {message}")
        return 0 if ok else 1

    print("Test écriture  : ignoré (clé indisponible ou non inscriptible)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
