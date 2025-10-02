#!/usr/bin/env bash
set -euo pipefail

USB_MOUNT_POINT="${USB_ROOT:-/mnt/usb}"
APP_USER="${APP_USER:-pi}"

if [[ $EUID -ne 0 ]]; then
    echo "Ce script doit être exécuté avec les droits administrateur (sudo)." >&2
    exit 1
fi

if ! id "$APP_USER" >/dev/null 2>&1; then
    echo "Utilisateur $APP_USER introuvable." >&2
    exit 1
fi

UID_VALUE="$(id -u "$APP_USER")"
GID_VALUE="$(id -g "$APP_USER")"

printf 'Utilisateur cible : %s (UID=%s, GID=%s)\n' "$APP_USER" "$UID_VALUE" "$GID_VALUE"
printf 'Point de montage attendu : %s\n' "$USB_MOUNT_POINT"

mkdir -p "$USB_MOUNT_POINT"
chmod 775 "$USB_MOUNT_POINT"

if getent group plugdev >/dev/null 2>&1; then
    if id -nG "$APP_USER" | grep -qw plugdev; then
        echo "L'utilisateur $APP_USER appartient déjà au groupe plugdev."
    else
        usermod -aG plugdev "$APP_USER"
        echo "Ajout de $APP_USER au groupe plugdev."
    fi
else
    echo "Groupe plugdev introuvable, aucune modification apportée."
fi

echo "Détection des périphériques USB disponibles..."
lsblk -f

BEST_DEVICE=""
BEST_FSTYPE=""
BEST_UUID=""
BEST_MOUNT=""

while read -r name fstype uuid mountpoint; do
    [[ -z "$name" ]] && continue
    device="/dev/$name"
    fstype_lc="${fstype,,}"
    if [[ "$mountpoint" == "$USB_MOUNT_POINT" ]]; then
        BEST_DEVICE="$device"
        BEST_FSTYPE="$fstype_lc"
        BEST_UUID="$uuid"
        BEST_MOUNT="$mountpoint"
        break
    fi
    if [[ -z "$BEST_DEVICE" && "$fstype_lc" =~ ^(vfat|fat|fat32|exfat|ntfs)$ && -n "$uuid" ]]; then
        BEST_DEVICE="$device"
        BEST_FSTYPE="$fstype_lc"
        BEST_UUID="$uuid"
        BEST_MOUNT="$mountpoint"
    fi
done < <(lsblk -rno NAME,FSTYPE,UUID,MOUNTPOINT)

if [[ -z "$BEST_DEVICE" ]]; then
    echo "Aucun périphérique USB compatible détecté. Branchez la clé puis relancez le script." >&2
    exit 1
fi

printf '\nPériphérique détecté : %s\n' "$BEST_DEVICE"
printf 'Type de système de fichiers : %s\n' "${BEST_FSTYPE:-inconnu}"
printf 'UUID : %s\n' "${BEST_UUID:-inconnu}"
printf 'Monté actuellement : %s\n\n' "${BEST_MOUNT:-non}" 

backup="/etc/fstab.backup.$(date +%Y%m%d_%H%M%S)"
cp /etc/fstab "$backup"
printf 'Sauvegarde de /etc/fstab : %s\n' "$backup"

if [[ -n "$BEST_UUID" ]]; then
    case "$BEST_FSTYPE" in
        vfat|fat|fat32)
            mount_type="vfat"
            mount_opts="defaults,uid=${UID_VALUE},gid=${GID_VALUE},umask=000,flush"
            ;;
        exfat)
            mount_type="exfat"
            mount_opts="defaults,uid=${UID_VALUE},gid=${GID_VALUE},umask=000"
            ;;
        ntfs)
            mount_type="ntfs"
            mount_opts="defaults,uid=${UID_VALUE},gid=${GID_VALUE},umask=000"
            ;;
        *)
            mount_type="${BEST_FSTYPE:-auto}"
            mount_opts="defaults,uid=${UID_VALUE},gid=${GID_VALUE},umask=022"
            ;;
    esac

    new_entry="UUID=${BEST_UUID} ${USB_MOUNT_POINT} ${mount_type} ${mount_opts} 0 0"
    if grep -q "${USB_MOUNT_POINT}" /etc/fstab || grep -q "${BEST_UUID}" /etc/fstab; then
        echo "Une entrée fstab existe déjà pour ${USB_MOUNT_POINT} ou l'UUID ${BEST_UUID}, aucune modification apportée."
    else
        echo "$new_entry" >> /etc/fstab
        echo "Entrée ajoutée à /etc/fstab : $new_entry"
    fi

    cat <<EXAMPLES

Exemples d'entrées /etc/fstab :
  vfat : UUID=${BEST_UUID} ${USB_MOUNT_POINT} vfat defaults,uid=${UID_VALUE},gid=${GID_VALUE},umask=000,flush 0 0
  exfat : UUID=${BEST_UUID} ${USB_MOUNT_POINT} exfat defaults,uid=${UID_VALUE},gid=${GID_VALUE},umask=000 0 0
  ntfs : UUID=${BEST_UUID} ${USB_MOUNT_POINT} ntfs defaults,uid=${UID_VALUE},gid=${GID_VALUE},umask=000 0 0
EXAMPLES
else
    echo "UUID non détecté. Vous devrez ajouter manuellement une entrée dans /etc/fstab."
fi

if mountpoint -q "$USB_MOUNT_POINT"; then
    echo "Le point ${USB_MOUNT_POINT} est déjà monté."
else
    echo "Montage de ${USB_MOUNT_POINT}..."
    mount "$USB_MOUNT_POINT" 2>/dev/null || true
fi

echo "Application des montages déclarés dans /etc/fstab..."
mount -a

echo "Configuration USB terminée."
