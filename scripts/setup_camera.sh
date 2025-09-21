#!/usr/bin/env bash
set -euo pipefail

if ! command -v sudo >/dev/null 2>&1; then
    echo "Ce script nécessite sudo pour installer les paquets." >&2
    exit 1
fi

PACKAGES=(
    python3-picamera2
    python3-opencv
    libcamera-apps
    v4l2loopback-utils
)

echo "[SETUP] Mise à jour des paquets..."
sudo apt update

echo "[SETUP] Installation des dépendances caméra: ${PACKAGES[*]}"
sudo apt install -y "${PACKAGES[@]}"

echo "[SETUP] Ajout de l'utilisateur ${USER} au groupe video"
sudo usermod -aG video "$USER"

echo "[SETUP] Vérification libcamera (capture test sans aperçu)"
if libcamera-still -n -o /tmp/simplebooth_test.jpg; then
    echo "[SETUP] Capture libcamera réussie → /tmp/simplebooth_test.jpg"
else
    echo "[SETUP] libcamera KO (voir les logs ci-dessus)"
fi

echo "[SETUP] Périphériques vidéo disponibles :"
ls -l /dev/video* 2>/dev/null || echo "Aucun périphérique /dev/video* détecté"

echo "[SETUP] Si l'utilisateur vient d'être ajouté au groupe video, redémarrez la session (logout/login) ou le Raspberry Pi."
