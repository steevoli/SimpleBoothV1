#!/usr/bin/env bash
set -euo pipefail

MOUNT_PATH="/media/steeve/31 GB Volume"
TARGET_USER=$(id -un)
TARGET_GROUP=$(id -gn)

if [[ $EUID -ne 0 ]]; then
  echo "[ERREUR] Ce script doit être exécuté avec les privilèges administrateur (ex: sudo)." >&2
  exit 1
fi

if [[ ! -d "$MOUNT_PATH" ]]; then
  echo "[ERREUR] Le chemin '$MOUNT_PATH' n'existe pas. Vérifiez que la clé USB est bien montée." >&2
  exit 1
fi

echo "Réattribution du dossier '$MOUNT_PATH' à $TARGET_USER:$TARGET_GROUP ..."
chown -R "$TARGET_USER:$TARGET_GROUP" "$MOUNT_PATH"

echo "Application des droits de lecture/écriture/exécution pour l'utilisateur ..."
chmod -R u+rwX "$MOUNT_PATH"

echo "Nettoyage des attributs d'accès bloquants (facultatif) ..."
find "$MOUNT_PATH" -type f -exec chmod u+rw {} +

sync

echo "Permissions mises à jour avec succès. Vous ne devriez plus voir le message d'erreur."
