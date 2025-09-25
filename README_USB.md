# Sauvegarde USB & Gestionnaire

## Détection USB
- **Linux / Raspberry Pi** : inspection des points de montage dans `/media/*/*` et `/run/media/*/*` en privilégiant le premier volume amovible disponible et en évitant les montages système (`boot`, `system`, `efi`, etc.).
- **Windows** : interrogation de l'API système (`GetLogicalDrives` / `GetDriveTypeW`) pour lister les lecteurs amovibles (ex. `E:\`, `F:\`). Un repli scanne les lettres `D:` à `Z:` si l'API n'est pas accessible.
- **macOS** : parcours des volumes présents dans `/Volumes/`.

La fonction utilitaire `get_usb_mount_point()` retourne le premier point de montage détecté ou `None` si aucune clé n'est disponible.

## Nouveautés UI
- Bouton **« Sauvegarder »** sur l'écran de révision : copie immédiatement la photo en cours dans `SimpleBooth/` à la racine de la clé USB avec un nom horodaté (`YYYYMMDD_HHMMSS.ext`). Un toast confirme la réussite ou signale l'erreur.
- Bouton **« Gérer USB »** sur l'écran principal : ouvre un gestionnaire listant les photos stockées sur la clé (aperçus, nom, taille, date). On peut rafraîchir la liste, pré-visualiser une photo, la supprimer (confirmation « Êtes-vous sûr ? ») ou fermer le panneau.
- Les notifications (« Photo sauvegardée… », « Aucune clé USB détectée… ») sont affichées en français via des toasts visuels.

## Limitations connues
- La création de miniatures exploite directement les fichiers originaux : de nombreuses images lourdes peuvent ralentir le chargement initial.
- Les suppressions utilisent une confirmation navigateur standard.
- Si aucune clé USB n'est branchée ou si les permissions manquent, l'interface affiche un message dédié et aucune action destructive n'est réalisée.

## Dépannage « Permission refusée »
Un utilitaire en ligne de commande est fourni pour diagnostiquer et corriger
les problèmes d'accès à la clé :

```bash
python scripts/usb_permission_fix.py
```

Le script détecte automatiquement la clé, vérifie que le dossier
`SimpleBooth/` est accessible en écriture puis tente plusieurs correctifs
(`remount,rw`, `chmod`). Consultez les logs pour connaître les actions menées
et effectuez, si nécessaire, les vérifications matérielles décrites dans la
documentation précédente.
