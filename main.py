# -*- coding: utf-8 -*-
"""
Application Principale - Système de Contrôle d'Accès Biométrique
=================================================================
Point d'entrée principal de l'application avec initialisation et configuration.

Auteur: Projet Biométrique
Version: 1.0
Date: Mars 2026

Fonctionnalités:
- Authentification par reconnaissance faciale
- Gestion des utilisateurs et autorisations
- Tatouage numérique des logs (LSB/DCT) pour garantir leur intégrité
- Alertes en cas d'accès non autorisé
- Historique consultable avec vérification de tatouage
- Conformité RGPD pour les données biométriques
"""

import sys
import os
import logging
from datetime import datetime

# Forcer l'encodage de la sortie standard en UTF-8 pour supporter les emojis sur Windows
try:
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


# Configurer le chemin d'import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'data', 'app.log'), encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def check_dependencies():
    """Vérifie que toutes les dépendances sont installées."""
    missing = []
    
    try:
        import cv2
    except ImportError:
        missing.append('opencv-python')
    
    try:
        import numpy
    except ImportError:
        missing.append('numpy')
    
    try:
        import PIL
    except ImportError:
        missing.append('Pillow')
    
    try:
        import sklearn
    except ImportError:
        missing.append('scikit-learn')
    
    try:
        import cv2.face
    except (ImportError, AttributeError):
        missing.append('opencv-contrib-python')
    
    if missing:
        print("=" * 60)
        print("DÉPENDANCES MANQUANTES")
        print("=" * 60)
        print("\nLes packages suivants doivent être installés:")
        for pkg in missing:
            print(f"  - {pkg}")
        print("\nInstallez-les avec la commande:")
        print(f"  pip install {' '.join(missing)}")
        print("\nOu utilisez requirements.txt:")
        print("  pip install -r requirements.txt")
        print("=" * 60)
        return False
    
    return True


def initialize_database():
    """Initialise la base de données avec les données par défaut."""
    try:
        from database import db_manager
        
        # Créer un utilisateur admin par défaut si aucun n'existe
        users = db_manager.get_all_users()
        if not users:
            existing_admin = db_manager.get_user(username="admin")
            if existing_admin:
                logger.info("Utilisateur admin déjà présent, création ignorée")
            else:
                logger.info("Création de l'utilisateur admin par défaut...")
                admin_id = db_manager.add_user(
                    username="admin",
                    full_name="Administrateur Système",
                    email="admin@example.com",
                    role="admin",
                    is_authorized=True,
                    consent_given=True
                )
                
                # Autoriser l'admin pour la zone principale
                zones = db_manager.get_zones()
                if zones:
                    db_manager.grant_authorization(admin_id, zones[0]['id'])
                
                logger.info(f"Utilisateur admin créé avec l'ID {admin_id}")
        
        logger.info("Base de données initialisée avec succès")
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la base de données: {e}")
        return False


def initialize_face_recognition():
    """Initialise le module de reconnaissance faciale."""
    try:
        from face_recognition_module import face_recognizer
        from database import db_manager
        
        # Charger les utilisateurs autorisés avec visages enregistrés
        users = db_manager.get_authorized_users()
        
        if users:
            logger.info(f"Chargement de {len(users)} profils utilisateurs...")
            face_recognizer.train_from_database(users)
            logger.info("Modèle de reconnaissance chargé avec succès")
        else:
            logger.warning("Aucun utilisateur avec visage enregistré trouvé")
        
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors de l'initialisation de la reconnaissance: {e}")
        return False


def run_cli_mode():
    """Mode ligne de commande pour les opérations de maintenance."""
    print("\n" + "=" * 60)
    print("SYSTÈME DE CONTRÔLE D'ACCÈS BIOMÉTRIQUE - MODE CLI")
    print("=" * 60)
    
    while True:
        print("\nOptions disponibles:")
        print("1. Ajouter un utilisateur")
        print("2. Lister les utilisateurs")
        print("3. Vérifier un log tatoué")
        print("4. Statistiques")
        print("5. Maintenance RGPD")
        print("6. Lancer l'interface graphique")
        print("0. Quitter")
        
        choice = input("\nVotre choix: ").strip()
        
        if choice == '0':
            print("Au revoir!")
            break
        elif choice == '1':
            _cli_add_user()
        elif choice == '2':
            _cli_list_users()
        elif choice == '3':
            _cli_verify_watermark()
        elif choice == '4':
            _cli_statistics()
        elif choice == '5':
            _cli_rgpd_maintenance()
        elif choice == '6':
            run_gui_mode()
            break
        else:
            print("Option invalide")


def _cli_add_user():
    """Ajoute un utilisateur en mode CLI."""
    from database import db_manager
    
    print("\n--- AJOUTER UN UTILISATEUR ---")
    username = input("Nom d'utilisateur: ").strip()
    full_name = input("Nom complet: ").strip()
    email = input("Email: ").strip()
    department = input("Département: ").strip()
    authorized = input("Autoriser l'accès? (o/n): ").strip().lower() == 'o'
    
    try:
        user_id = db_manager.add_user(
            username=username,
            full_name=full_name,
            email=email,
            department=department,
            is_authorized=authorized,
            consent_given=True
        )
        print(f"\n✓ Utilisateur créé avec l'ID {user_id}")
    except Exception as e:
        print(f"\n✗ Erreur: {e}")


def _cli_list_users():
    """Liste les utilisateurs en mode CLI."""
    from database import db_manager
    
    print("\n--- LISTE DES UTILISATEURS ---")
    users = db_manager.get_all_users(active_only=False)
    
    if not users:
        print("Aucun utilisateur trouvé")
        return
    
    print(f"\n{'ID':<5} {'Nom':<25} {'Email':<30} {'Autorisé':<10} {'Visage':<8}")
    print("-" * 80)
    
    for user in users:
        authorized = "Oui" if user['is_authorized'] else "Non"
        has_face = "Oui" if user['face_encoding'] else "Non"
        print(f"{user['id']:<5} {user['full_name']:<25} {user['email'] or '-':<30} {authorized:<10} {has_face:<8}")


def _cli_verify_watermark():
    """Vérifie un tatouage en mode CLI."""
    from watermark_module import watermark_manager
    
    print("\n--- VÉRIFIER UN LOG TATOUÉ ---")
    filepath = input("Chemin de l'image: ").strip()
    
    if not os.path.exists(filepath):
        print("Fichier non trouvé")
        return
    
    result = watermark_manager.verify_log_integrity(filepath)
    
    print("\nRésultat:")
    if result['is_valid']:
        print("✓ TATOUAGE VALIDE - Intégrité vérifiée")
    else:
        print("✗ TATOUAGE INVALIDE")
    
    print(f"Message: {result['message']}")
    if result['data']:
        print(f"Données: {result['data']}")


def _cli_statistics():
    """Affiche les statistiques en mode CLI."""
    from database import db_manager
    
    print("\n--- STATISTIQUES ---")
    stats = db_manager.get_statistics(days=30)
    
    print(f"\nPériode: 30 derniers jours")
    print(f"Total des accès: {stats.get('total_access', 0)}")
    print(f"Utilisateurs actifs: {stats.get('active_users', 0)}")
    print(f"Utilisateurs autorisés: {stats.get('authorized_users', 0)}")
    print(f"Alertes en attente: {stats.get('pending_alerts', 0)}")
    
    print("\nRépartition par type:")
    for access_type, count in stats.get('by_type', {}).items():
        print(f"  • {access_type}: {count}")


def _cli_rgpd_maintenance():
    """Maintenance RGPD en mode CLI."""
    from database import db_manager
    import config
    
    print("\n--- MAINTENANCE RGPD ---")
    print(f"Politique actuelle:")
    print(f"  - Anonymisation après: {config.RGPD['anonymize_after_days']} jours")
    print(f"  - Suppression après: {config.RGPD['data_retention_days']} jours")
    
    if input("\nExécuter la maintenance? (o/n): ").strip().lower() == 'o':
        anonymized = db_manager.anonymize_old_data()
        deleted = db_manager.delete_old_logs()
        print(f"\n✓ {anonymized} enregistrements anonymisés")
        print(f"✓ {deleted} anciens logs supprimés")


def run_gui_mode():
    """Lance l'interface graphique."""
    logger.info("Lancement de l'interface graphique...")
    
    try:
        import tkinter as tk
        from gui_application import AccessControlApp
        
        root = tk.Tk()
        app = AccessControlApp(root)
        
        logger.info("Application démarrée avec succès")
        root.mainloop()
        
    except Exception as e:
        logger.error(f"Erreur lors du lancement de l'interface: {e}")
        raise


def main():
    """Point d'entrée principal de l'application."""
    print("\n" + "=" * 60)
    print("SYSTÈME DE CONTRÔLE D'ACCÈS BIOMÉTRIQUE")
    print("=" * 60)
    print(f"Démarrage: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Vérifier les dépendances
    logger.info("Vérification des dépendances...")
    if not check_dependencies():
        sys.exit(1)
    
    # Créer le dossier data s'il n'existe pas
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # Initialiser la base de données
    logger.info("Initialisation de la base de données...")
    if not initialize_database():
        logger.error("Échec de l'initialisation de la base de données")
        sys.exit(1)
    
    # Initialiser la reconnaissance faciale
    logger.info("Initialisation du module de reconnaissance faciale...")
    initialize_face_recognition()
    
    # Déterminer le mode de lancement
    if len(sys.argv) > 1 and sys.argv[1] == '--cli':
        run_cli_mode()
    else:
        run_gui_mode()


if __name__ == "__main__":
    main()
