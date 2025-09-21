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

2. **Lancer le backend caméra (Plan B MJPEG + santé)**
   ```bash
   python3 server/app.py
   ```
   Ce service écoute par défaut sur `http://localhost:8080` et expose :
   - `/camera/stream` : flux MJPEG de secours utilisable directement (`<img src="http://localhost:8080/camera/stream">`).
   - `/camera/health` : diagnostic JSON (présence Picamera2, groupe video, /dev/video*, dernier frame, erreurs récentes).

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

Le frontal tente désormais automatiquement deux plans complémentaires :

- **Plan A – WebRTC (getUserMedia)** :
  1. Contrainte minimale `{ video: true }`
  2. Contrainte 1080p `{ video: { width: { ideal: 1920 }, height: { ideal: 1080 } } }`
  3. Contrainte ciblée sur le `deviceId` choisi dans la liste déroulante.
  Les erreurs détaillées (`NotAllowedError`, `NotReadableError`, etc.) sont affichées dans une bannière, et un bouton "Re-tester" relance la séquence.

- **Plan B – Flux MJPEG** :
  Si tous les essais WebRTC échouent, le composant bascule automatiquement sur le flux `/camera/stream` du backend. Un badge "Plan B (MJPEG)" indique le mode actif.

### Outil de diagnostic intégré

- Bouton "Diagnostic caméra" dans l'interface principale.
- Affiche la liste des périphériques vidéo détectés par le navigateur (`enumerateDevices`).
- Interroge `/camera/health` et affiche l'état (module Picamera2 présent, appartenance au groupe video, `/dev/video*`, horodatage du dernier frame, erreurs récentes).
- Journalisation enrichie côté console (front et backend) pour faciliter la résolution d'incidents.

### Bonnes pratiques

- Après ajout au groupe `video`, redémarrer la session utilisateur ou le Raspberry Pi.
- Débrancher/rebrancher une webcam USB problématique et relancer le diagnostic.
- En cas d'absence totale de caméra, le diagnostic indique précisément la cause (module manquant, droits, périphériques absents).

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
