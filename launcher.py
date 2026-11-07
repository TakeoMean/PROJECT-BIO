# -*- coding: utf-8 -*-
"""
Lanceur Principal - Menu d'Accès Rapide
=====================================
Interface simple pour accéder à tous les outils du système.
"""

import os
import subprocess
import sys
from pathlib import Path


def clear_screen():
    """Efface l'écran de la console."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    """Affiche la bannière principale."""
    banner = """
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║   🔐 SYSTÈME DE CONTRÔLE D'ACCÈS BIOMÉTRIQUE                  ║
║                                                                ║
║   Reconnaissance faciale • Anti-Spoofing • Tatouage Numérique  ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_menu():
    """Affiche le menu principal."""
    menu = """
┌──────────────────────────────────────────────────────────────┐
│ MENU PRINCIPAL                                               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ 🚀 DÉMARRAGE                                                │
│   1. Initialisation du système (première utilisation)      │
│   2. Valider le système (tests)                            │
│                                                              │
│ 📸 DONNÉES                                                   │
│   3. Capturer données d'entraînement (300 images)          │
│   4. Générer dataset synthétique (TEST)                    │
│                                                              │
│ 🎮 APPLICATION                                              │
│   5. Lancer l'application                                  │
│                                                              │
│ ⚙️  OUTILS                                                   │
│   6. Ajouter un utilisateur (CLI)                          │
│   7. Lister les utilisateurs                               │
│   8. Entraîner le modèle                                   │
│   9. Exporter les logs                                     │
│                                                              │
│ 📚 DOCUMENTATION                                            │
│   10. Afficher le guide de configuration                   │
│   11. Afficher le guide complet                            │
│                                                              │
│ 0. Quitter                                                 │
│                                                              │
└──────────────────────────────────────────────────────────────┘
    """
    print(menu)


def run_command(script_name, description):
    """Exécute un script Python."""
    try:
        print(f"\n{'='*60}")
        print(f"🔄 {description}")
        print(f"{'='*60}\n")
        
        result = subprocess.run(
            [sys.executable, script_name],
            cwd=os.path.dirname(__file__) or '.'
        )
        
        if result.returncode != 0:
            print(f"\n⚠️  Attention: Script terminé avec le code {result.returncode}")
        else:
            print(f"\n✅ {description} - Terminé!")
            
    except FileNotFoundError:
        print(f"❌ Erreur: Le fichier {script_name} n'a pas été trouvé!")
    except KeyboardInterrupt:
        print(f"\n⏹️  {description} annulée par l'utilisateur")
    except Exception as e:
        print(f"❌ Erreur: {e}")


def show_file(filename, title):
    """Affiche le contenu d'un fichier."""
    filepath = os.path.join(os.path.dirname(__file__) or '.', filename)
    
    if not os.path.exists(filepath):
        print(f"❌ Fichier {filename} non trouvé!")
        return
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"\n{'='*60}")
        print(f"📄 {title}")
        print(f"{'='*60}\n")
        print(content)
        
        input("\n[Appuyez sur ENTRÉE pour continuer...]")
        
    except Exception as e:
        print(f"❌ Erreur lecture fichier: {e}")


def quick_start_wizard():
    """Assistant de démarrage rapide."""
    clear_screen()
    print_banner()
    
    print("""
╔════════════════════════════════════════════════════════════════╗
║ ⚡ ASSISTANT DE DÉMARRAGE RAPIDE                              ║
╚════════════════════════════════════════════════════════════════╝

Ce qui va se passer:
1. ✅ Vérification des dépendances
2. ✅ Initialisation de la base de données
3. ✅ Validation du système
4. ✅ Prêt à l'emploi!

Voulez-vous continuer? (o/n): """)
    
    response = input().strip().lower()
    
    if response == 'o':
        print("\n🔄 Initialisation...")
        run_command('init_advanced.py', "Initialisation du système")
        
        print("\n🔄 Validation...")
        run_command('validate_system.py', "Validation du système")
        
        print(f"""
{'='*60}
✅ ASSISTANT TERMINÉ!
{'='*60}

Prochaines étapes:

1. CAPTURER LES DONNÉES (très important!)
   python launcher.py → Choix 3

2. LANCER L'APPLICATION
   python launcher.py → Choix 5

💡 Conseil: Capturez au moins 300 images par utilisateur pour
   une meilleure reconnaissance!

{'='*60}
        """)


def main():
    """Fonction principale du lanceur."""
    
    while True:
        clear_screen()
        print_banner()
        print_menu()
        
        choice = input("\n👉 Votre choix: ").strip()
        
        if choice == '0':
            print("\n👋 Au revoir!")
            break
            
        elif choice == '1':
            run_command('init_advanced.py', "Initialisation du système")
            
        elif choice == '2':
            run_command('validate_system.py', "Validation du système")
            
        elif choice == '3':
            run_command('training_data_generator.py', "Capturer les données d'entraînement")
            
        elif choice == '4':
            print("\n" + "="*60)
            print("Génération de dataset synthétique")
            print("="*60)
            print("""
Ce mode génère des images synthétiques pour le test.
Utilisez-le si vous n'avez pas accès à une caméra.

Nombre d'utilisateurs (défaut 5): """)
            num_users_input = input().strip()
            num_users = int(num_users_input) if num_users_input else 5
            
            print("Images par utilisateur (défaut 60): ")
            images_input = input().strip()
            images = int(images_input) if images_input else 60
            
            # Créer le script synthétique
            from training_data_generator import TrainingDataGenerator
            gen = TrainingDataGenerator()
            gen.generate_synthetic_dataset(num_users, images)
            
            input("\n[Appuyez sur ENTRÉE pour continuer...]")
            
        elif choice == '5':
            run_command('main.py', "Lancement de l'application")
            
        elif choice == '6':
            print("\n" + "="*60)
            print("Ajouter un utilisateur (Mode CLI)")
            print("="*60)
            run_command('main.py', "Application")
            
        elif choice == '7':
            print("\n" + "="*60)
            print("Liste des utilisateurs")
            print("="*60)
            try:
                from database import db_manager
                users = db_manager.get_all_users()
                
                if not users:
                    print("❌ Aucun utilisateur trouvé")
                else:
                    print(f"\n{'ID':<5} {'Nom':<25} {'Email':<30} {'Autorisé':<10}")
                    print("-" * 70)
                    for user in users:
                        authorized = "✅" if user['is_authorized'] else "❌"
                        print(f"{user['id']:<5} {user['full_name']:<25} {user['email'] or '-':<30} {authorized:<10}")
                    print(f"\nTotal: {len(users)} utilisateurs")
            except Exception as e:
                print(f"❌ Erreur: {e}")
            
            input("\n[Appuyez sur ENTRÉE pour continuer...]")
            
        elif choice == '8':
            print("\n" + "="*60)
            print("Entraînement du modèle")
            print("="*60)
            try:
                from database import db_manager
                from face_recognition_module import face_recognizer
                
                users = db_manager.get_authorized_users()
                print(f"Utilisateurs autorisés: {len(users)}")
                
                if users:
                    print("🔄 Entraînement en cours...")
                    success = face_recognizer.train_from_database(users)
                    if success:
                        print("✅ Modèle entraîné avec succès!")
                    else:
                        print("⚠️  Entraînement partiel")
                else:
                    print("❌ Aucun utilisateur autorisé")
            except Exception as e:
                print(f"❌ Erreur: {e}")
            
            input("\n[Appuyez sur ENTRÉE pour continuer...]")
            
        elif choice == '9':
            print("\n" + "="*60)
            print("Export des logs")
            print("="*60)
            try:
                from database import db_manager
                
                logs = db_manager.get_access_logs(limit=100)
                
                # Créer un fichier CSV
                import csv
                from datetime import datetime
                
                filename = f"logs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['ID', 'Utilisateur', 'Zone', 'Type', 'Résultat', 'Confiance', 'Timestamp'])
                    
                    for log in logs:
                        writer.writerow([
                            log['id'],
                            log.get('user_id', 'N/A'),
                            log.get('zone_id', 'N/A'),
                            log['access_type'],
                            log['access_result'],
                            log.get('confidence_score', 'N/A'),
                            log['timestamp']
                        ])
                
                print(f"✅ Logs exportés vers: {filename}")
                print(f"   Nombre de logs: {len(logs)}")
            except Exception as e:
                print(f"❌ Erreur: {e}")
            
            input("\n[Appuyez sur ENTRÉE pour continuer...]")
            
        elif choice == '10':
            show_file('config.py', "Configuration du système")
            
        elif choice == '11':
            show_file('SETUP_GUIDE.md', "Guide d'utilisation complet")
            
        else:
            print("❌ Option invalide!")
            input("\n[Appuyez sur ENTRÉE pour continuer...]")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Arrêt du programme")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erreur critique: {e}")
        sys.exit(1)
