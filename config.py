# -*- coding: utf-8 -*-
"""
Configuration du Système de Contrôle d'Accès Biométrique
=========================================================
Fichier de configuration centralisé pour tous les paramètres du système.
"""

import os
import sys

# Forcer l'encodage de la sortie standard en UTF-8 pour supporter les emojis sur Windows
try:
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# =============================================================================
# CHEMINS DU PROJET
# =============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "data", "access_control.db")
FACES_DIR = os.path.join(BASE_DIR, "data", "faces")
LOGS_DIR = os.path.join(BASE_DIR, "data", "logs")
CAPTURES_DIR = os.path.join(BASE_DIR, "data", "captures")
WATERMARKED_LOGS_DIR = os.path.join(BASE_DIR, "data", "watermarked_logs")

# Créer les dossiers s'ils n'existent pas
for directory in [FACES_DIR, LOGS_DIR, CAPTURES_DIR, WATERMARKED_LOGS_DIR, 
                  os.path.join(BASE_DIR, "data")]:
    os.makedirs(directory, exist_ok=True)

# =============================================================================
# PARAMÈTRES DE RECONNAISSANCE FACIALE
# =============================================================================
FACE_RECOGNITION = {
    "cascade_path": "haarcascade_frontalface_default.xml",
    "min_face_size": (40, 40),
    "scale_factor": 1.1,
    "min_neighbors": 5,
    "confidence_threshold": 25.0,  # Seuil de confiance stricte pour LBP (plus strict = ne reconnaît que les visages similaires)
    "max_distance": 0.055,  # Distance maximale réduite (plus strict pour rejeter les visages inconnus)
    "fallback_distance": 0.070,  # Distance tolérée pour stabiliser une reconnaissance
    "stability_hold_seconds": 1.5,  # Durée de maintien de la reconnaissance
    "min_stable_confidence": 22.0,  # Confiance minimale pour un maintien temporaire
    "training_images_per_user": 20,
    "recognition_timeout": 5.0,  # Secondes max pour la reconnaissance
}

# =============================================================================
# PARAMÈTRES D'ANTI-USURPATION (ANTI-SPOOFING)
# =============================================================================
ANTI_SPOOFING = {
    "enabled": True,
    "method": "multi",
    "confidence_threshold": 0.65,  # STRONGER threshold to detect spoofing - more strict
    "min_passed_checks": 1,  # Only 1 method needs to pass
    "block_on_low_texture_and_frequency": False,
    
    # Texture Analysis (LBP - Local Binary Patterns)
    "texture": {
        "enabled": True,
        "threshold": 0.55,  # Stricter - photos have less texture variation
        "weight": 0.25,  # Increased weight
    },
    
    # Color Space Analysis (HSV color distribution)
    "color": {
        "enabled": True,
        "threshold": 0.50,  # Stricter for detecting color inconsistencies in photos
        "weight": 0.20,  # Increased weight
    },
    
    # Frequency Domain Analysis (FFT)
    "frequency": {
        "enabled": True,
        "threshold": 0.55,  # Stricter - real faces have higher frequency content
        "weight": 0.30,  # Increased weight - most effective method
    },

    # Screen Glare Detection (phone/tablet display)
    "glare": {
        "enabled": True,
        "threshold": 0.45,  # More sensitive to detect screens
        "weight": 0.25,  # Increased weight
        "v_threshold": 0.80,  # More sensitive brightness detection
        "s_threshold": 0.30,  # More sensitive saturation detection
        "ratio_norm": 0.10,
        "hard_ratio": 0.15,
    },
    
    # Motion Detection (Optical Flow)
    "motion": {
        "enabled": False,  # Keep disabled for now
        "threshold": 0.40,
        "weight": 0.10,
        "required_frames": 5,
    },
    
    # Face Liveness Detection
    "liveness": {
        "enabled": True,
        "eye_blink_threshold": 0.3,
        "head_movement_threshold": 5.0,
    },
}

# =============================================================================
# PARAMÈTRES DE PERFORMANCE ET OPTIMISATION
# =============================================================================
PERFORMANCE = {
    "frame_skip": 2,  # Traiter 1 frame tous les N frames (1 = tous, 2 = un sur deux)
    "resize_scale": 1.0,  # Ne pas réduire la taille pour assurer une bonne détection
    "max_detection_time": 5.0,  # Timeout de détection en secondes
    "cache_enabled": True,  # Activer la mise en cache des visages détectés
    "lazy_loading": True,  # Charger les modèles à la demande
    "threading": True,  # Traitement multi-thread
    "gpu_acceleration": False,  # Utiliser GPU si disponible
}

# =============================================================================
# PARAMÈTRES DE FLEXIBILITÉ ET RÉSILIENCE
# =============================================================================
FLEXIBILITY = {
    "retry_on_fail": True,  # Réessayer en cas d'erreur
    "max_retries": 3,
    "fallback_to_liveness": True,  # Basculer sur détection de vivacité
    "auto_brightness_adjust": True,  # Ajuster automatiquement la luminosité
    "auto_contrast_adjust": True,  # Ajuster automatiquement le contraste
    "multi_face_handling": "largest",  # "largest", "closest" ou "all"
    "recover_on_error": True,  # Reprendre après une erreur
    "degraded_mode": True,  # Mode dégradé si les services secondaires échouent
}

# =============================================================================
# PARAMÈTRES DE LOGGING ET DEBUGGING
# =============================================================================
LOGGING = {
    "debug_mode": False,  # Mode debug (verbose logging)
    "log_frames": False,  # Sauvegarder les frames d'entrée
    "log_detections": True,  # Enregistrer les détections
    "save_spoofing_analysis": False,  # Sauvegarder l'analyse anti-spoofing
    "performance_monitoring": True,  # Monitorer les performances
    "log_level": "INFO",  # INFO, WARNING, ERROR, DEBUG
}

# =============================================================================
# PARAMÈTRES DE TATOUAGE NUMÉRIQUE
# =============================================================================
WATERMARK = {
    "method": "LSB",  # "LSB" ou "DCT"
    "lsb_bits": 2,  # Nombre de bits LSB utilisés
    "dct_strength": 25,  # Force du tatouage DCT
    "secret_key": os.environ.get("BIO_WATERMARK_SECRET_KEY", ""),
    "block_size": 8,  # Taille des blocs pour DCT
}

# =============================================================================
# PARAMÈTRES DE NOTIFICATION EMAIL (SMTP)
# =============================================================================
EMAIL = {
    "enabled": os.environ.get("BIO_EMAIL_ENABLED", "false").strip().lower() in ("1", "true", "yes", "on"),
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": os.environ.get("BIO_SENDER_EMAIL", ""),
    "sender_password": os.environ.get("BIO_SENDER_PASSWORD", ""),
    "admin_emails": [
        address.strip()
        for address in os.environ.get("BIO_ADMIN_EMAILS", "").split(",")
        if address.strip()
    ],
    "use_tls": True,
}

# =============================================================================
# PARAMÈTRES DE SÉCURITÉ
# =============================================================================
SECURITY = {
    "max_failed_attempts": 3,  # Tentatives avant alarme
    "lockout_duration": 300,  # Durée du verrouillage en secondes
    "session_timeout": 3600,  # Timeout de session en secondes
    "require_admin_password": True,
    "admin_password_hash": None,  # À définir lors de la première utilisation
}

# =============================================================================
# PARAMÈTRES D'AFFICHAGE
# =============================================================================
UI = {
    "window_title": "Système de Contrôle d'Accès Biométrique",
    "window_size": "1200x800",
    "theme": "default",
    "camera_index": 0,
    "camera_width": 640,
    "camera_height": 480,
    "fps": 30,
}

# =============================================================================
# TYPES D'ACCÈS
# =============================================================================
ACCESS_TYPES = {
    "AUTHORIZED": "Utilisateur autorisé - Accès accordé",
    "KNOWN_UNAUTHORIZED": "Utilisateur connu - Accès refusé",
    "IMPOSTOR": "Imposteur détecté - Alarme déclenchée",
    "UNKNOWN": "Personne inconnue détectée",
}

# =============================================================================
# NIVEAUX D'ALERTE
# =============================================================================
ALERT_LEVELS = {
    "INFO": 0,
    "WARNING": 1,
    "CRITICAL": 2,
    "ALARM": 3,
}

# =============================================================================
# RGPD - CONFORMITÉ
# =============================================================================
RGPD = {
    "data_retention_days": 90,  # Durée de conservation des logs
    "anonymize_after_days": 30,  # Anonymisation après X jours
    "export_format": "json",  # Format d'export des données personnelles
    "consent_required": True,  # Consentement obligatoire
}
