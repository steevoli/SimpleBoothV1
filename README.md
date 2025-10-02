# 📸 Photobooth Raspberry Pi

> **Application Flask pour photobooth tactile avec flux vidéo temps réel, capture instantanée, effets IA et intégration Telegram**

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-2.3.3-green.svg)
![Raspberry Pi](https://img.shields.io/badge/Raspberry%20Pi-Compatible-red.svg)
![Runware](https://img.shields.io/badge/Runware%20AI-Intégré-purple.svg)
![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)
![OpenCV](https://img.shields.io/badge/OpenCV-Support%20USB-brightgreen.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## 🎯 Aperçu

Cette application transforme votre Raspberry Pi en un photobooth professionnel avec :
- **Flux vidéo temps réel** en MJPEG 1280x720 (16:9)
- **Support multi-caméras** : Pi Camera ou caméra USB
- **Interface tactile optimisée** pour écran 7 pouces
- **Capture photo instantanée** directement depuis le flux vidéo
- **Effets IA** via l'API Runware pour transformer vos photos
- **Diaporama automatique** configurable après période d'inactivité
- **Bot Telegram** pour envoi automatique des photos sur un groupe/canal
- **Impression thermique** avec texte personnalisable
- **Interface d'administration** complète

## 🔧️ Matériel requis

### Matériel supporté

- **Caméra** : 
  - Raspberry Pi Camera (v1, v2, v3, HQ)
  - Caméra USB standard (webcam)
- **Écran tactile** : Écran 7 pouces recommandé
- **Imprimante thermique Serie** : Compatible avec le script `ScriptPythonPOS.py`

### 🛒 Liens d'achat (Affiliation)

Voici une liste de matériel compatible. Les liens sont affiliés et aident à soutenir le projet.

- **Raspberry Pi & Accessoires :**
  - [Raspberry Pi 5](https://amzlink.to/az0ncNNUsGjUH)
  - [Alimentation Raspberry Pi 5](https://amzlink.to/az01ijEmlFqxT)
- **Caméras :**
  - [Pi Camera 3](https://amzlink.to/az0eEXwhnxNvO)
  - [Pi Camera 2.1](https://amzlink.to/az0mgp7Sob1xh)
- **Imprimantes Thermiques :**
  - [Imprimante Thermique (Amazon)](https://amzlink.to/az0wTKS9Bfig2)
  - [Imprimante Thermique (AliExpress)](https://s.click.aliexpress.com/e/_oFyCgCI)
  - [Imprimante Thermique (France)](https://www.gotronic.fr/art-imprimante-thermique-ada597-21349.htm)
- **Écran :**
  - [Ecran Waveshare (Amazon)](https://amzlink.to/az03G4UMruNnc)

### Installation

### 🚀 Installation

L'installation peut se faire de deux manières : automatiquement via un script (recommandé sur Raspberry Pi) ou manuellement.

#### Méthode 1 : Installation automatique avec `setup.sh` (Recommandé)

Un script `setup.sh` est fourni pour automatiser l'ensemble du processus sur un système basé sur Debian (comme Raspberry Pi OS).

1.  **Rendre le script exécutable :**
    ```bash
    chmod +x setup.sh
    ```

2.  **Lancer le script d'installation :**
    ```bash
    ./setup.sh
    ```
    Ce script s'occupe de :
    - Mettre à jour les paquets système.
    - Installer les dépendances système (`libcamera-apps`, `python3-opencv`).
    - Créer un environnement virtuel `venv`.
    - Installer les dépendances Python de `requirements.txt` dans cet environnement.
    - Creer un mode kiosk automatique au demarrage du systeme.

    Le mode kiosk démarre Chromium en plein écran avec les options suivantes pour éviter toute demande manuelle d'autorisation caméra/micro :

    ```bash
    chromium-browser --kiosk --no-sandbox --noerrdialogs --disable-infobars \
      --use-fake-ui-for-media-stream \
      --autoplay-policy=no-user-gesture-required \
      http://localhost:5000
    ```

    ⚠️ **Important :** ces options acceptent automatiquement l'accès aux périphériques audio/vidéo. Ne les activez pas sur une machine exposée à Internet.

#### Méthode 2 : Installation manuelle

Suivez ces étapes pour une installation manuelle.

1.  **Créer et activer un environnement virtuel :**
    Il est fortement recommandé d'utiliser un environnement virtuel pour isoler les dépendances du projet.
    ```bash
    # Créer l'environnement
    python3 -m venv venv

    # Activer l'environnement
    source venv/bin/activate
    ```
    > Pour quitter l'environnement virtuel, tapez simplement `deactivate`.

2.  **Sur Raspberry Pi, installer les dépendances système :**
    Si vous ne l'avez pas déjà fait, installez les paquets nécessaires pour les caméras.
    ```bash
    sudo apt update
    sudo apt upgrade
    sudo apt install libcamera-apps python3-opencv
    ```

3.  **Installer les dépendances Python :**
    ```bash
    pip install -r requirements.txt
    ```

## Utilisation

1. **Préparer la caméra (à faire une seule fois)**
   - Activer la caméra via `sudo raspi-config` (Interface Options → Camera) et redémarrer si demandé.
   - Lancer le script d'installation caméra :
     ```bash
     chmod +x scripts/setup_camera.sh
     ./scripts/setup_camera.sh
     ```
     Ce script installe `python3-picamera2`, `python3-opencv`, `libcamera-apps`, ajoute l'utilisateur au groupe `video` et teste `libcamera-still`.
   - Sur Chromium/Kiosk, autoriser explicitement l'accès à la caméra pour l'URL du photobooth.

2. **Installer et lancer le service caméra local (port 8080)**

   Installer les dépendances système nécessaires à Picamera2 :

   ```bash
   sudo apt update
   sudo apt install -y python3-picamera2 libcamera-tools
   ```

   Puis installer les dépendances Python du micro-service (idéalement dans un environnement virtuel) :

   ```bash
   pip install -r camera_service/requirements.txt
   ```

   Lancer manuellement le service pour un test rapide :

   ```bash
   python3 camera_service/app.py
   ```

   Il écoute sur `http://localhost:8080` et expose :
   - `GET /health` → état JSON de la caméra (`ok`, message d'erreur en cas d'indisponibilité).
   - `GET /snapshot` → capture instantanée au format JPEG.

   Vérifier que tout fonctionne :

   ```bash
   curl http://localhost:8080/health
   curl -o test.jpg http://localhost:8080/snapshot
   ```

### 📂 Gestion de la clé USB

L'application recherche automatiquement une clé USB montée dans :

1. `/media/<utilisateur>/*`
2. `/media/*`
3. `/run/media/*`

Le premier dossier monté et accessible en écriture est retenu comme **`USB_ROOT`**, puis le sous-dossier **`USB_ROOT/sauvegardes`** est créé au besoin. Pour forcer un chemin précis (par exemple avec des espaces), définissez la variable d'environnement :

```bash
export USB_ROOT="/media/steeve/31 GB Volume"
```

Un lien symbolique `/mnt/usb` est créé automatiquement pour conserver la compatibilité avec les anciens scripts, mais l'application n'en dépend plus.

#### Préparer la clé

1. **Monter la clé avec les bons droits**

   ```bash
   sudo ./install_usb.sh
   ```

   Ce script détecte la clé, propose une entrée `/etc/fstab`, ajoute l'utilisateur courant au groupe `plugdev` et applique le montage (`mount -a`).

2. **Vérifier les montages disponibles**

   ```bash
   lsblk -f
   ```

   Les exemples d'entrées `/etc/fstab` restent valables, quel que soit le point de montage réel :

   ```fstab
   UUID=<UUID> /mnt/usb vfat defaults,uid=<UID>,gid=<GID>,umask=000,flush 0 0
   UUID=<UUID> /mnt/usb exfat defaults,uid=<UID>,gid=<GID>,umask=000 0 0
   UUID=<UUID> /mnt/usb ntfs defaults,uid=<UID>,gid=<GID>,umask=000 0 0
   ```

#### Vérifier l'accès depuis l'API

```bash
curl -s http://localhost:5000/usb/health | jq
curl -s -X POST http://localhost:5000/usb/mkdir \
     -H 'Content-Type: application/json' \
     -d '{"path":"sauvegardes/tests"}'
curl -s -X POST http://localhost:5000/save \
     -H 'Content-Type: application/json' \
     -d '{"filename":"test.txt","encoding":"text","content":"Hello USB"}'
curl -s http://localhost:5000/usb/list?path=sauvegardes | jq
```

La route `GET /usb/health` renvoie un objet `{ ok, path, mounted, writable, free_bytes, ... }` et fournit des codes d'erreur explicites (`503` si la clé est absente, `507` si l'espace libre est insuffisant, etc.).

#### Diagnostic rapide

```bash
python3 diagnostic_usb.py
```

Ce script affiche le chemin détecté, l'état courant et effectue un test d'écriture/suppression dans `sauvegardes/.__test__`.

   Pour un démarrage automatique au boot, installer le service systemd fourni :

   ```bash
   sudo cp camera-service.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now camera-service
   ```

   Contrôle du service :

   ```bash
   sudo systemctl status camera-service
   sudo journalctl -u camera-service -f
   ```

3. **Lancer l'application principale :**
   ```bash
   python3 app.py
   ```

4. **Accéder à l'interface :**
   - Ouvrir un navigateur sur `http://localhost:5000`
   - Ou depuis un autre appareil : `http://[IP_RASPBERRY]:5000`

5. **Administration :**
   - Accéder à `/admin` pour configurer l'application

## Configuration des caméras

Le frontal utilise désormais une fonction unique `takePhoto()` qui combine automatiquement deux stratégies :

- **Plan A – WebRTC (getUserMedia)** : tentative d'ouverture de la caméra navigateur avec la contrainte `{ video: { facingMode: "environment" } }`. En cas de succès, le flux est affiché dans la balise `<video>` et la capture se fait via un `<canvas>` local.
- **Plan B – Capture HTTP** : si l'accès navigateur échoue (refus utilisateur, périphérique occupé, absence de caméra), l'application bascule sur le service local `http://localhost:8080/snapshot`. L'image JPEG renvoyée est affichée dans l'aperçu et utilisée pour la sauvegarde côté serveur.

Avant chaque déclenchement, `takePhoto()` interroge `http://localhost:8080/health` pour afficher le statut "Caméra locale prête / indisponible" dans le badge en haut à droite. La bannière d'alerte s'adapte automatiquement :

- "Caméra navigateur refusée → bascule sur capture système (8080)…" lorsque l'utilisateur refuse la permission.
- "Service caméra indisponible (8080). Vérifie qu'il tourne : sudo systemctl status camera-service." lorsque le micro-service est arrêté ou occupé.

### Outil de diagnostic intégré

- Bouton "Diagnostic caméra" dans l'interface principale.
- Affiche la liste des périphériques vidéo détectés par le navigateur (`enumerateDevices`).
- Interroge `/camera/health` et affiche l'état (module Picamera2 présent, appartenance au groupe video, `/dev/video*`, horodatage du dernier frame, erreurs récentes).
- Journalisation enrichie côté console (front et backend) pour faciliter la résolution d'incidents.

### Bonnes pratiques

- Après ajout au groupe `video`, redémarrer la session utilisateur ou le Raspberry Pi.
- Débrancher/rebrancher une webcam USB problématique et relancer le diagnostic.
- En cas d'absence totale de caméra, le diagnostic indique précisément la cause (module manquant, droits, périphériques absents).
- Pour éviter la popup de permission, ouvrir Chromium sur `http://localhost:5000` et autoriser la caméra de manière permanente (icône cadenas) ou lancer le navigateur en mode kiosque avec `--use-fake-ui-for-media-stream`.

## 📂 Structure des fichiers

Le projet est organisé de manière modulaire pour une meilleure maintenance :

```
SimpleBooth/
├── app.py                 # Application Flask principale (routes, logique)
├── camera_utils.py        # Utilitaires pour la gestion des caméras (Pi Camera, USB)
├── config_utils.py        # Utilitaires pour charger/sauvegarder la configuration
├── telegram_utils.py      # Utilitaires pour l'envoi de messages via le bot Telegram
├── ScriptPythonPOS.py     # Script autonome pour l'impression thermique
├── setup.sh               # Script d'installation automatisée pour Raspberry Pi
├── requirements.txt       # Dépendances Python
├── camera_service/        # Service Flask Picamera2 (port 8080)
│   ├── app.py
│   └── requirements.txt
├── camera-service.service # Unité systemd pour le service caméra
├── static/                # Fichiers statiques
│   └── camera-placeholder.svg
├── templates/             # Templates HTML (Jinja2)
│   ├── index.html         # Interface principale du photobooth
│   ├── review.html        # Page de prévisualisation et d'action post-capture
│   ├── admin.html         # Panneau d'administration
│   └── base.html          # Template de base commun
├── photos/                # Dossier pour les photos originales (créé au lancement)
├── effet/                 # Dossier pour les photos avec effets (créé au lancement)
└── config.json            # Fichier de configuration (créé au lancement)
```

## Configuration

La configuration est sauvegardée dans `config.json` :

### Général
- `footer_text` : Texte en pied de photo
- `timer_seconds` : Délai avant capture (1-10 secondes)
- `high_density` : Qualité d'impression haute densité

### Diaporama
- `slideshow_enabled` : Activer/désactiver le diaporama automatique
- `slideshow_delay` : Délai d'inactivité avant affichage du diaporama (10-300 secondes)
- `slideshow_source` : Source des photos pour le diaporama ('photos' ou 'effet')

### Effets IA
- `effect_enabled` : Activer/désactiver les effets IA
- `effect_prompt` : Description textuelle de l'effet IA souhaité
- `effect_steps` : Nombre d'étapes de génération IA (1-50, plus = meilleure qualité mais plus lent)
- `runware_api_key` : Clé API Runware pour l'accès au service IA

### Bot Telegram
- `telegram_enabled` : Activer/désactiver le bot Telegram
- `telegram_bot_token` : Token du bot obtenu via @BotFather
- `telegram_chat_id` : ID du chat/groupe/canal de destination
- `telegram_send_type` : Type de photos à envoyer ('photos', 'effet' ou 'both')


## Configuration du bot Telegram

1. **Créer un bot** : 
   - Contactez [@BotFather](https://t.me/BotFather) sur Telegram
   - Envoyez `/newbot` et suivez les instructions
   - Notez le token fourni (format: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

2. **Obtenir l'ID du chat** :
   
   Pour un chat privé :
   - Envoyez un message à [@userinfobot](https://t.me/userinfobot) pour obtenir votre ID
   
   Pour un groupe :
   - Ajoutez le bot au groupe d'abord!
   - ID format: `-123456789` (notez le signe négatif)
   - Utilisez [@GroupIDbot](https://t.me/GroupIDbot) pour trouver l'ID
   
   Pour un canal :
   - Ajoutez le bot comme administrateur du canal
   - Format canal public: `@nom_du_canal`
   - Format canal privé: `-100123456789`

3. **Configurer dans l'admin** :
   - Activez l'option Telegram
   - Entrez le token du bot et l'ID du chat
   - Choisissez le type de photos à envoyer (originales, effet, ou les deux)

## Dépannage

- **Caméra non détectée** : Vérifier que la caméra est activée dans `raspi-config`
- **Erreur d'impression** : Vérifier la connexion de l'imprimante thermique et TX/RX
- **Effets IA ne fonctionnent pas** : Vérifier la validité de la clé API Runware
- **"Chat not found" dans Telegram** : 
  - Vérifier que le bot est bien membre du groupe/canal
  - Format correct de l'ID (numérique pour privé, commence par `-` pour groupe)
  - Le bot doit être admin pour les canaux
- **Dossier effet manquant** : L'application le crée automatiquement au démarrage
