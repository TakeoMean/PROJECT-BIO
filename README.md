# Système de Contrôle d'Accès Biométrique avec Tatouage des Logs

## 📋 Description

Application complète de contrôle d'accès par reconnaissance faciale intégrant un mécanisme de preuve d'intégrité des journaux d'accès via tatouage numérique robuste.

### Fonctionnalités principales

- ✅ **Authentification par reconnaissance faciale** - Temps réel < 2 secondes
- ✅ **Gestion des utilisateurs et autorisations** - CRUD complet
- ✅ **Tatouage numérique des logs** - Méthodes LSB et DCT
- ✅ **Alertes en cas d'accès non autorisé** - Notifications email
- ✅ **Historique consultable** - Avec vérification de tatouage
- ✅ **Conformité RGPD** - Anonymisation et suppression automatique

## 🏗️ Architecture

| Composant | Technologie |
|-----------|-------------|
| Interface | Python + Tkinter |
| Reconnaissance | OpenCV + scikit-learn |
| Tatouage | LSB ou DCT sur les logs |
| Base de données | SQLite |
| Notifications | Email (SMTP) |

## 📁 Structure du projet

```
PROJECT BIO/
├── main.py                    # Point d'entrée principal
├── config.py                  # Configuration centralisée
├── database.py                # Module base de données SQLite
├── face_recognition_module.py # Module de reconnaissance faciale
├── watermark_module.py        # Module de tatouage numérique
├── notification_module.py     # Module de notifications
├── gui_application.py         # Interface graphique Tkinter
├── requirements.txt           # Dépendances Python
├── README.md                  # Documentation
└── data/                      # Données de l'application
    ├── access_control.db      # Base de données SQLite
    ├── faces/                 # Images de visages enregistrés
    ├── captures/              # Captures d'accès
    ├── watermarked_logs/      # Logs tatoués
    └── app.log                # Fichier de log
```

## 🚀 Installation

### Prérequis

- Python 3.8 ou supérieur
- Webcam fonctionnelle
- Windows 10/11 (ou Linux/macOS avec adaptations)

### Installation des dépendances

```bash
# Cloner ou copier le projet
cd "PROJECT BIO"

# Installer les dépendances
pip install -r requirements.txt
```

### Dépendances principales

- `opencv-python` >= 4.8.0
- `opencv-contrib-python` >= 4.8.0
- `numpy` >= 1.24.0
- `Pillow` >= 10.0.0
- `scikit-learn` >= 1.3.0

## 💻 Utilisation

### Lancement de l'application

```bash
# Mode graphique (par défaut)
python main.py

# Mode ligne de commande
python main.py --cli
```

### Guide rapide

1. **Démarrer la caméra** - Cliquez sur "Démarrer Caméra"
2. **Ajouter un utilisateur** - Onglet "Utilisateurs" > "Ajouter"
3. **Enregistrer un visage** - Sélectionner l'utilisateur > "Enregistrer visage"
4. **Activer la reconnaissance** - Cliquez sur "Activer Reconnaissance"

## 🔐 Types d'accès

| Type | Description | Action |
|------|-------------|--------|
| `AUTHORIZED` | Utilisateur reconnu et autorisé | Accès enregistré + log tatoué |
| `KNOWN_UNAUTHORIZED` | Utilisateur connu non autorisé | Alerte + log tatoué |
| `IMPOSTOR` | Personne non reconnue | Alarme + capture + log tatoué |
| `UNKNOWN` | Détection sans reconnaissance | Log + notification |

## 🖼️ Tatouage Numérique

### Méthode LSB (Least Significant Bit)

- Modification des bits de poids faible de l'image
- Invisible à l'œil nu
- Capacité élevée
- Sensible à la compression JPEG forte

### Méthode DCT (Discrete Cosine Transform)

- Modification dans le domaine fréquentiel
- Plus robuste à la compression
- Utilisé pour les applications critiques

### Vérification d'intégrité

```python
from watermark_module import watermark_manager

# Vérifier un log tatoué
result = watermark_manager.verify_log_integrity("chemin/vers/image.png")
print(f"Valide: {result['is_valid']}")
print(f"Données: {result['data']}")
```

## ⚙️ Configuration

Fichier `config.py` :

Les parametres sensibles sont lus depuis les variables d'environnement :

- `BIO_WATERMARK_SECRET_KEY` : cle aleatoire longue, requise pour creer ou verifier les tatouages.
- `BIO_EMAIL_ENABLED` : `true` pour activer les notifications email (desactive par defaut).
- `BIO_SENDER_EMAIL` et `BIO_SENDER_PASSWORD` : identifiants SMTP.
- `BIO_ADMIN_EMAILS` : adresses des administrateurs, separees par des virgules.

Exemple PowerShell (les valeurs ne doivent pas etre ajoutees a Git) :

```powershell
$env:BIO_WATERMARK_SECRET_KEY = "<your-long-random-secret>"
$env:BIO_SENDER_EMAIL = "you@example.com"
$env:BIO_SENDER_PASSWORD = "<your-app-password>"
$env:BIO_ADMIN_EMAILS = "admin@example.com"
$env:BIO_EMAIL_ENABLED = "true"
```

Les bases de donnees, journaux, captures, donnees faciales et modeles locaux sous `data/` sont exclus de Git.
```

## 📊 API Base de données

```python
from database import db_manager

# Ajouter un utilisateur
user_id = db_manager.add_user(
    username="jdoe",
    full_name="John Doe",
    email="john@example.com",
    is_authorized=True
)

# Récupérer les logs
logs = db_manager.get_access_logs(limit=100)

# Statistiques
stats = db_manager.get_statistics(days=30)
```

## 🛡️ Conformité RGPD

- **Consentement** : Obligatoire avant enregistrement biométrique
- **Anonymisation** : Automatique après 30 jours (configurable)
- **Suppression** : Logs supprimés après 90 jours
- **Export** : Données utilisateur exportables sur demande

## 📧 Notifications

Les alertes sont envoyées par email pour :
- Accès non autorisé d'un utilisateur connu
- Détection d'imposteur (alarme critique)
- Rapport quotidien (optionnel)

## 🧪 Tests de robustesse du tatouage

```python
from watermark_module import watermark_manager

results = watermark_manager.test_robustness("image_tatouee.png")
# Teste: compression JPEG, redimensionnement, bruit, luminosité
```

## 📝 Contraintes techniques respectées

- ✅ Traitement en temps réel (< 2 secondes par reconnaissance)
- ✅ Robustesse aux variations d'éclairage (CLAHE + prétraitement)
- ✅ Conformité RGPD pour les données biométriques
- ✅ Intégrité des logs vérifiable par extraction du tatouage

## 🐛 Dépannage

### La caméra ne s'ouvre pas
```bash
# Vérifier que la caméra n'est pas utilisée par une autre application
# Tester avec:
python -c "import cv2; cap = cv2.VideoCapture(0); print(cap.isOpened())"
```

### Erreur opencv-contrib-python
```bash
pip uninstall opencv-python opencv-contrib-python
pip install opencv-contrib-python
```

### Module cv2.face non trouvé
```bash
pip install opencv-contrib-python --upgrade
```

## 📄 Licence

Projet éducatif - Mars 2026

## 👥 Auteurs

Projet Biométrique - Système de Contrôle d'Accès
