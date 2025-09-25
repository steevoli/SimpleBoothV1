#!/usr/bin/env python3
"""Outil de diagnostic et de correction des permissions USB.

Ce script tente de détecter la clé USB utilisée par l'application,
valide qu'elle est accessible en lecture / écriture puis applique
plusieurs correctifs courants en cas d'échec.

Usage::

    python scripts/usb_permission_fix.py

Le script est idempotent et peut être relancé après chaque branchement
de la clé.
"""
from __future__ import annotations

import argparse
import logging
import os
import platform
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Optional

# Les utilitaires existants gèrent la détection multiplateforme.
from storage_usb import ensure_usb_folder_exists, get_usb_mount_point

logger = logging.getLogger("usb_permission_fix")


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")


def _check_writable(path: Path) -> bool:
    """Retourne True si l'on peut écrire dans ``path``."""

    try:
        path.mkdir(parents=True, exist_ok=True)
        test_file = path / ".usb_write_test.tmp"
        with open(test_file, "wb") as handle:
            handle.write(b"usb")
        test_file.unlink()
        return True
    except OSError as exc:
        logger.debug("Écriture impossible dans %s: %s", path, exc)
        return False


def _try_linux_remount_rw(mount_point: Path) -> bool:
    """Tentative de remonter le volume en lecture/écriture (Linux)."""

    if platform.system().lower() != "linux":
        return False

    try:
        subprocess.run(
            ["sudo", "mount", "-o", "remount,rw", str(mount_point)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        logger.info("Montage remount,rw exécuté avec succès")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        logger.warning("Remontage en lecture/écriture impossible: %s", exc)
        return False


def _try_chmod(mount_point: Path) -> bool:
    """Ajuste les permissions pour autoriser la lecture/écriture."""

    try:
        os.chmod(mount_point, 0o775)
        logger.info("Permissions mises à jour sur %s", mount_point)
        return True
    except PermissionError as exc:
        logger.warning("Impossible de modifier les permissions: %s", exc)
        return False


def _diagnose(mount_point: Path) -> None:
    """Affiche un diagnostic détaillé."""

    logger.info("Point de montage détecté: %s", mount_point)
    logger.info("Système: %s", platform.platform())
    logger.info("Droits actuels: %s", oct(mount_point.stat().st_mode & 0o777))

    subfolder = mount_point / "SimpleBooth"
    writable = _check_writable(subfolder)
    if writable:
        logger.info("Le dossier %s est accessible en écriture", subfolder)
    else:
        logger.error("Le dossier %s n'est pas accessible en écriture", subfolder)


def _run_fix_sequence(mount_point: Path) -> bool:
    """Enchaîne différentes corrections et retourne True si OK."""

    subfolder = mount_point / "SimpleBooth"
    if _check_writable(subfolder):
        return True

    logger.info("Tentative de correction des permissions USB…")

    # 1. Forcer le dossier attendu par l'application.
    try:
        ensure_usb_folder_exists()
    except Exception as exc:
        logger.debug("Création du dossier SimpleBooth impossible: %s", exc)

    # 2. Remonter en lecture/écriture sur Linux.
    if _try_linux_remount_rw(mount_point) and _check_writable(subfolder):
        return True

    # 3. Ajuster les permissions Unix.
    if _try_chmod(mount_point) and _check_writable(subfolder):
        return True

    # 4. Dernier essai: chmod directement le sous-dossier.
    if subfolder.exists():
        try:
            os.chmod(subfolder, 0o775)
            logger.info("Permissions mises à jour sur %s", subfolder)
        except PermissionError as exc:
            logger.warning("Impossible de modifier %s: %s", subfolder, exc)
    return _check_writable(subfolder)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnostique et corrige les erreurs 'Permission refusée' sur la clé USB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Étapes exécutées:
              1. Détection du point de montage USB.
              2. Vérification de l'écriture dans le dossier SimpleBooth/.
              3. Tentative de correction (remount/chmod) si nécessaire.

            Relancez le script après avoir reconnecté la clé ou modifié ses permissions.
            """
        ),
    )
    parser.add_argument("--verbose", action="store_true", help="Affiche les logs détaillés")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    _configure_logging(args.verbose)

    mount_point = get_usb_mount_point()
    if not mount_point:
        logger.error("Aucune clé USB détectée. Branchez la clé puis relancez le script.")
        return 1

    _diagnose(mount_point)

    if _run_fix_sequence(mount_point):
        logger.info("La clé USB est maintenant accessible en lecture/écriture.")
        return 0

    logger.error(
        "Les corrections automatiques ont échoué. Vérifiez manuellement le formatage ou les droits "
        "(clé verrouillée, système de fichiers en lecture seule, etc.)."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
