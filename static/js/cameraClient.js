const CONSTRAINT_ATTEMPTS = [
    {
        name: "Basique",
        constraints: { video: true, audio: false }
    },
    {
        name: "Idéal 1080p",
        constraints: {
            video: {
                width: { ideal: 1920 },
                height: { ideal: 1080 }
            },
            audio: false
        }
    }
];

function formatError(error) {
    if (!error) {
        return "Erreur inconnue";
    }
    const name = error.name || error.constructor?.name || "Erreur";
    const message = error.message || String(error);
    return `${name}: ${message}`;
}

function createLogPrefix() {
    const now = new Date().toISOString();
    return `[cameraClient ${now}]`;
}

export class CameraClient {
    constructor(options) {
        this.videoElement = options.videoElement;
        this.fallbackImage = options.fallbackImage;
        this.planBBadge = options.planBBadge;
        this.errorBanner = options.errorBanner;
        this.errorBannerText = options.errorBannerText;
        this.errorBannerDetails = options.errorBannerDetails;
        this.deviceSelect = options.deviceSelect;
        this.diagnosticsModal = options.diagnosticsModal;
        this.diagnosticsDevicesList = options.diagnosticsDevicesList;
        this.diagnosticsHealthPre = options.diagnosticsHealthPre;
        this.diagnosticsTimestamp = options.diagnosticsTimestamp;
        this.retryButton = options.retryButton;
        this.diagnosticButton = options.diagnosticButton;

        this.currentStream = null;
        this.availableDevices = [];
        this.lastErrors = [];
        this.isPlanBActive = false;

        const defaultServer = window.SIMPLEBOOTH_CAMERA_SERVER
            || `${window.location.protocol}//${window.location.hostname}:8080`;
        this.cameraServerBase = options.cameraServerBase || defaultServer;

        this.handleVisibilityChange = this.handleVisibilityChange.bind(this);
        this.handleDeviceChange = this.handleDeviceChange.bind(this);
        this.handleRetry = this.handleRetry.bind(this);
        this.handleDiagnosticClick = this.handleDiagnosticClick.bind(this);
    }

    log(...args) {
        console.log(createLogPrefix(), ...args);
    }

    warn(...args) {
        console.warn(createLogPrefix(), ...args);
    }

    error(...args) {
        console.error(createLogPrefix(), ...args);
    }

    async initialise() {
        this.attachEventListeners();
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.displayError("API getUserMedia indisponible.");
            this.enablePlanB();
            return;
        }

        await this.refreshDeviceList();
        await this.tryStartStream();
    }

    attachEventListeners() {
        document.addEventListener("visibilitychange", this.handleVisibilityChange);
        if (navigator.mediaDevices && navigator.mediaDevices.addEventListener) {
            navigator.mediaDevices.addEventListener("devicechange", this.handleDeviceChange);
        }
        if (this.deviceSelect) {
            this.deviceSelect.addEventListener("change", () => {
                const deviceId = this.deviceSelect.value || null;
                this.tryStartStream(deviceId);
            });
        }
        if (this.retryButton) {
            this.retryButton.addEventListener("click", this.handleRetry);
        }
        if (this.diagnosticButton) {
            this.diagnosticButton.addEventListener("click", this.handleDiagnosticClick);
        }
    }

    detachEventListeners() {
        document.removeEventListener("visibilitychange", this.handleVisibilityChange);
        if (navigator.mediaDevices && navigator.mediaDevices.removeEventListener) {
            navigator.mediaDevices.removeEventListener("devicechange", this.handleDeviceChange);
        }
        if (this.retryButton) {
            this.retryButton.removeEventListener("click", this.handleRetry);
        }
        if (this.diagnosticButton) {
            this.diagnosticButton.removeEventListener("click", this.handleDiagnosticClick);
        }
    }

    handleVisibilityChange() {
        if (document.hidden) {
            this.stopStream();
        } else {
            this.tryStartStream(this.deviceSelect?.value || null);
        }
    }

    async handleDeviceChange() {
        this.log("Changement de périphérique détecté, actualisation de la liste...");
        await this.refreshDeviceList();
        await this.tryStartStream(this.deviceSelect?.value || null);
    }

    async handleRetry() {
        this.log("Nouvelle tentative d'accès à la caméra demandée");
        this.hideError();
        await this.tryStartStream(this.deviceSelect?.value || null, true);
    }

    async handleDiagnosticClick() {
        await this.runDiagnostics();
        if (this.diagnosticsModal) {
            const modalLib = window.bootstrap;
            const modal = modalLib?.Modal?.getOrCreateInstance(this.diagnosticsModal);
            modal?.show();
        }
    }

    async refreshDeviceList() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
            this.warn("enumerateDevices non disponible");
            return;
        }
        try {
            const devices = await navigator.mediaDevices.enumerateDevices();
            this.availableDevices = devices.filter((d) => d.kind === "videoinput");
            this.updateDeviceSelect();
        } catch (error) {
            this.error("Erreur enumerateDevices", error);
            this.displayError(`Impossible de lister les périphériques vidéo: ${formatError(error)}`);
        }
    }

    updateDeviceSelect() {
        if (!this.deviceSelect) {
            return;
        }
        const currentValue = this.deviceSelect.value;
        this.deviceSelect.innerHTML = "";

        if (!this.availableDevices.length) {
            const option = document.createElement("option");
            option.value = "";
            option.textContent = "Aucune caméra détectée";
            this.deviceSelect.appendChild(option);
            this.deviceSelect.disabled = true;
            return;
        }

        this.deviceSelect.disabled = false;
        this.availableDevices.forEach((device, index) => {
            const option = document.createElement("option");
            option.value = device.deviceId;
            const label = device.label || `Caméra ${index + 1}`;
            option.textContent = `${label} (${device.deviceId || "ID inconnu"})`;
            this.deviceSelect.appendChild(option);
        });

        if (currentValue) {
            const existing = Array.from(this.deviceSelect.options).find(
                (option) => option.value === currentValue
            );
            if (existing) {
                this.deviceSelect.value = currentValue;
            }
        }
    }

    async tryStartStream(preferredDeviceId = null, forceRestart = false) {
        if (!forceRestart && this.currentStream && !this.isPlanBActive) {
            this.log("Flux existant actif, aucune action nécessaire");
            return;
        }

        this.stopStream();
        this.isPlanBActive = false;

        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.displayError("API getUserMedia indisponible.");
            this.enablePlanB();
            return;
        }

        const attempts = [...CONSTRAINT_ATTEMPTS];
        if (preferredDeviceId) {
            attempts.push({
                name: `Périphérique sélectionné`,
                constraints: {
                    video: {
                        deviceId: { exact: preferredDeviceId }
                    },
                    audio: false
                }
            });
        }

        this.lastErrors = [];

        for (const attempt of attempts) {
            try {
                this.log(`Tentative getUserMedia (${attempt.name})`, attempt.constraints);
                const stream = await navigator.mediaDevices.getUserMedia(attempt.constraints);
                await this.attachStream(stream, attempt.name);
                this.hideError();
                return;
            } catch (error) {
                this.lastErrors.push({ attempt: attempt.name, error });
                this.error(`getUserMedia échoue (${attempt.name})`, error);
                this.displayError(formatError(error), attempt.name);
            }
        }

        this.warn("Toutes les tentatives WebRTC ont échoué, bascule en plan B");
        this.enablePlanB();
    }

    async attachStream(stream, attemptName) {
        this.log(`Flux WebRTC obtenu via ${attemptName}`);
        this.stopStream();
        this.currentStream = stream;

        if (this.videoElement) {
            this.videoElement.srcObject = stream;
            this.videoElement.classList.remove("d-none");
            this.videoElement.play().catch((err) => {
                this.warn("Impossible de lancer la lecture vidéo", err);
            });
        }

        if (this.fallbackImage) {
            this.fallbackImage.classList.add("d-none");
        }
        if (this.planBBadge) {
            this.planBBadge.classList.add("d-none");
        }
        this.isPlanBActive = false;
    }

    stopStream() {
        if (this.currentStream) {
            this.currentStream.getTracks().forEach((track) => {
                try {
                    track.stop();
                } catch (error) {
                    this.warn("Erreur lors de l'arrêt d'une piste", error);
                }
            });
            this.currentStream = null;
        }
        if (this.videoElement) {
            this.videoElement.srcObject = null;
        }
    }

    enablePlanB() {
        if (this.videoElement) {
            this.videoElement.classList.add("d-none");
            this.videoElement.srcObject = null;
        }
        if (this.fallbackImage) {
            const bust = Date.now();
            const url = `${this.cameraServerBase}/camera/stream?ts=${bust}`;
            this.fallbackImage.src = url;
            this.fallbackImage.classList.remove("d-none");
        }
        if (this.planBBadge) {
            this.planBBadge.classList.remove("d-none");
        }
        this.isPlanBActive = true;
    }

    displayError(message, attemptName = null) {
        if (!this.errorBanner || !this.errorBannerText) {
            return;
        }
        const fullMessage = attemptName ? `${attemptName} → ${message}` : message;
        this.errorBannerText.textContent = fullMessage;
        if (this.errorBannerDetails) {
            this.errorBannerDetails.innerHTML = this.lastErrors
                .map((entry) => `• ${entry.attempt}: ${formatError(entry.error)}`)
                .join("<br>");
        }
        this.errorBanner.classList.remove("d-none");
    }

    hideError() {
        if (this.errorBanner) {
            this.errorBanner.classList.add("d-none");
        }
    }

    async runDiagnostics() {
        this.log("Exécution du diagnostic caméra...");
        await this.refreshDeviceList();
        if (this.diagnosticsDevicesList) {
            this.diagnosticsDevicesList.innerHTML = "";
            if (!this.availableDevices.length) {
                this.diagnosticsDevicesList.innerHTML = "<li class=\"list-group-item\">Aucun périphérique vidéo détecté.</li>";
            } else {
                this.availableDevices.forEach((device, index) => {
                    const li = document.createElement("li");
                    li.className = "list-group-item";
                    const label = device.label || `Caméra ${index + 1}`;
                    li.textContent = `${label} — ${device.deviceId || "ID inconnu"}`;
                    this.diagnosticsDevicesList.appendChild(li);
                });
            }
        }

        const now = new Date();
        if (this.diagnosticsTimestamp) {
            this.diagnosticsTimestamp.textContent = now.toLocaleString();
        }

        if (this.diagnosticsHealthPre) {
            this.diagnosticsHealthPre.textContent = "Chargement...";
            try {
                const response = await fetch(`${this.cameraServerBase}/camera/health`);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                const data = await response.json();
                this.diagnosticsHealthPre.textContent = JSON.stringify(data, null, 2);
            } catch (error) {
                const message = `Impossible de joindre ${this.cameraServerBase}/camera/health → ${formatError(error)}`;
                this.diagnosticsHealthPre.textContent = message;
                this.error(message);
            }
        }
    }
}
