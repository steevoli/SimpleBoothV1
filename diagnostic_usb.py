#!/usr/bin/env python3
"""Script de diagnostic pour le stockage USB du photobooth."""
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from usb_utils import USB_ROOT, check_usb_health, pretty_print_health


def run_command(command):
    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        return exc.stderr.strip() or str(exc)
    except FileNotFoundError:
        return f"Commande introuvable: {' '.join(command)}"


def format_permissions(path: Path) -> str:
    try:
        st = path.stat()
    except FileNotFoundError:
        return "Chemin introuvable"

    mode = stat.filemode(st.st_mode)
    try:
        import pwd
        import grp

        owner = pwd.getpwuid(st.st_uid).pw_name
        group = grp.getgrgid(st.st_gid).gr_name
    except Exception:
        owner = str(st.st_uid)
        group = str(st.st_gid)
    return f"{mode} {owner}:{group}"


def test_write(path: Path) -> str:
    if not path.exists():
        return "Le dossier n'existe pas."
    try:
        with tempfile.NamedTemporaryFile(dir=path, prefix="usb_test_", delete=False) as tmp:
            tmp.write(b"diagnostic")
            temp_path = Path(tmp.name)
        temp_path.unlink(missing_ok=True)
        return "Succès : écriture autorisée."
    except PermissionError as exc:
        return f"Permission refusée: {exc}"
    except OSError as exc:
        return f"Erreur système: {exc}"


def read_fstab_entries(mount_point: Path) -> str:
    fstab = Path('/etc/fstab')
    if not fstab.exists():
        return "/etc/fstab introuvable"
    lines = []
    for line in fstab.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        if str(mount_point) in stripped:
            lines.append(stripped)
    if not lines:
        return "Aucune entrée dédiée trouvée."
    return '\n'.join(lines)


def main() -> int:
    print("=== Diagnostic USB ===")
    print(f"Point de montage attendu : {USB_ROOT}")

    health = check_usb_health(test_write=True)
    print("\n--- État rapporté par l'application ---")
    print(pretty_print_health(health))

    print("\n--- lsblk -f ---")
    print(run_command(['lsblk', '-f']))

    print("\n--- Entrées /etc/fstab ---")
    print(read_fstab_entries(USB_ROOT))

    print("\n--- Permissions du dossier ---")
    print(format_permissions(USB_ROOT))

    print("\n--- Test d'écriture ---")
    print(test_write(USB_ROOT))

    return 0


if __name__ == '__main__':
    sys.exit(main())
