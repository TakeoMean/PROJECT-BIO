# -*- coding: utf-8 -*-
"""
Test Complet du Système
======================
Démontre le flux complet: reconnaissance faciale + anti-spoofing + logs.
"""

import cv2
import numpy as np
import sys
import time
from datetime import datetime

import config
from face_recognition_module import face_recognizer
from anti_spoofing_module import anti_spoofing_detector
from database import db_manager


def demo_face_detection():
    """Démontre la détection faciale."""
    print("\n" + "="*60)
    print("DÉMO 1: DÉTECTION FACIALE")
    print("="*60)
    print("""
Cet exemple capture des visages depuis la caméra
et affiche les détails de chaque détection.

Positionnez-vous devant la caméra...
Pressez ESC pour arrêter.
    """)
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Caméra non accessible!")
        return False
    
    detection_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        faces = face_recognizer.detect_faces(frame)
        
        # Dessiner les rectangles
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        
        # Afficher les informations
        cv2.putText(frame, f"Visages: {len(faces)}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, "ESC pour quitter", (10, 70),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
        
        if faces:
            detection_count += 1
            print(f"✅ {len(faces)} visage(s) détecté(s) - Frame {detection_count}")
        
        cv2.imshow("Détection Faciale", frame)
        
        if cv2.waitKey(1) & 0xFF == 27:  # ESC
            break
    
    cap.release()
    cv2.destroyAllWindows()
    
    print(f"✅ Démonstration terminée - {detection_count} frames avec visages")
    return detection_count > 0


def demo_anti_spoofing():
    """Démontre la détection anti-spoofing."""
    print("\n" + "="*60)
    print("DÉMO 2: ANTI-SPOOFING (DÉTECTION USURPATION)")
    print("="*60)
    print("""
Cet exemple teste la détection anti-spoofing.
Essayez avec:
  1. Votre vrai visage
  2. Une photo imprimée
  3. Une vidéo sur écran

Pressez ESC pour arrêter.
    """)
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Caméra non accessible!")
        return False
    
    test_count = 0
    real_detections = 0
    spoofing_detections = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        faces = face_recognizer.detect_faces(frame)
        
        if faces:
            x, y, w, h = faces[0]
            face_color = face_recognizer.extract_face(frame, faces[0], grayscale=False)
            
            # Tester anti-spoofing
            result = anti_spoofing_detector.detect_spoofing(frame, face_color)
            
            test_count += 1
            is_real = result['is_real']
            confidence = result['confidence']
            
            if is_real:
                real_detections += 1
                color = (0, 255, 0)  # Vert
                status = "✅ RÉEL"
            else:
                spoofing_detections += 1
                color = (0, 0, 255)  # Rouge
                status = "❌ USURPATION"
            
            # Afficher sur l'image
            cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
            cv2.putText(frame, f"{status} ({confidence:.1%})", (x, y-10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            
            # Afficher les détails
            details = result.get('details', {})
            y_offset = 60
            for key, val in details.items():
                if isinstance(val, (int, float)):
                    cv2.putText(frame, f"{key}: {val:.2f}", (10, y_offset),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
                    y_offset += 30
            
            print(f"Test {test_count}: {status} (Confiance: {confidence:.1%})")
            print(f"  Détails: {details}")
        
        cv2.putText(frame, "ESC pour quitter", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
        
        cv2.imshow("Anti-Spoofing", frame)
        
        if cv2.waitKey(1) & 0xFF == 27:  # ESC
            break
    
    cap.release()
    cv2.destroyAllWindows()
    
    print(f"""
✅ Démonstration terminée
   Total tests: {test_count}
   Visages réels: {real_detections}
   Usurpations: {spoofing_detections}
    """)
    
    return test_count > 0


def demo_full_recognition():
    """Démontre la reconnaissance faciale complète."""
    print("\n" + "="*60)
    print("DÉMO 3: RECONNAISSANCE FACIALE COMPLÈTE")
    print("="*60)
    print("""
Cet exemple effectue la reconnaissance complète:
  1. Détection du visage
  2. Vérification anti-spoofing
  3. Reconnaissance de l'utilisateur
  4. Enregistrement du log

Pressez ESC pour arrêter.
    """)
    
    # Charger le modèle
    if not face_recognizer.is_trained:
        print("⚠️  Modèle non entraîné - utilisation du mode de détection seul")
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Caméra non accessible!")
        return False
    
    recognition_count = 0
    last_record_time = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Reconnaissance complète
        results = face_recognizer.recognize(frame)
        
        if results:
            for result in results:
                recognition_count += 1
                
                x, y, w, h = result['face_rect']
                confidence = result['confidence']
                is_real = result.get('is_real', True)
                spoofing_conf = result.get('spoofing_confidence', 1.0)
                user_id = result.get('user_id')
                
                # Déterminer la couleur et le status
                if not is_real:
                    color = (0, 0, 255)  # Rouge - Spoofing
                    status = "USURPATION"
                    user_name = "N/A"
                elif result['recognized']:
                    color = (0, 255, 0)  # Vert - Reconnu
                    status = f"ID: {user_id}"
                    user = db_manager.get_user(user_id=user_id)
                    user_name = user['full_name'] if user else f"ID {user_id}"
                else:
                    color = (0, 165, 255)  # Orange - Inconnu
                    status = "INCONNU"
                    user_name = "?"
                
                # Afficher les résultats
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
                cv2.putText(frame, f"{user_name}", (x, y-30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                cv2.putText(frame, f"Conf: {confidence:.1f}% | Anti-Spoof: {spoofing_conf:.1%}",
                           (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                
                # Afficher dans le terminal
                print(f"✅ Test {recognition_count}:")
                print(f"   Utilisateur: {user_name}")
                print(f"   Confiance: {confidence:.1f}%")
                print(f"   Anti-spoofing: {spoofing_conf:.1%}")
                print(f"   Statut: {status}")
                print()
        
        cv2.putText(frame, "ESC pour quitter", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
        
        cv2.imshow("Reconnaissance Complète", frame)
        
        if cv2.waitKey(1) & 0xFF == 27:  # ESC
            break
    
    cap.release()
    cv2.destroyAllWindows()
    
    print(f"\n✅ Démonstration terminée - {recognition_count} reconnaissances effectuées")
    return recognition_count > 0


def demo_database():
    """Démontre les capacités de la base de données."""
    print("\n" + "="*60)
    print("DÉMO 4: BASE DE DONNÉES")
    print("="*60)
    
    try:
        # Statistiques générales
        users = db_manager.get_all_users()
        authorized_users = db_manager.get_authorized_users()
        logs = db_manager.get_access_logs(limit=10)
        zones = db_manager.get_zones()
        
        print(f"""
✅ Statistiques de la base de données:
   
   Utilisateurs totaux: {len(users)}
   Utilisateurs autorisés: {len(authorized_users)}
   Zones d'accès: {len(zones)}
   Derniers logs: {len(logs)}
   
Utilisateurs:
        """)
        
        for user in users:
            authorized = "✅" if user['is_authorized'] else "❌"
            has_face = "📷" if user['face_encoding'] else "❌"
            print(f"  - {user['full_name']:<25} {authorized} {has_face}")
        
        print(f"\nDerniers accès:")
        for log in logs[:5]:
            user_id = log.get('user_id', '?')
            access_type = log['access_type']
            timestamp = log['timestamp']
            print(f"  - User {user_id}: {access_type} ({timestamp})")
        
        print("\n✅ Base de données fonctionnelle")
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


def demo_performance():
    """Démontre les performances du système."""
    print("\n" + "="*60)
    print("DÉMO 5: TEST DE PERFORMANCE")
    print("="*60)
    
    try:
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("❌ Caméra non accessible!")
            return False
        
        print("\nMesurage des performances sur 30 frames...")
        
        times = {
            'detection': [],
            'spoofing': [],
            'total': []
        }
        
        for i in range(30):
            ret, frame = cap.read()
            if not ret:
                break
            
            start_total = time.time()
            
            # Détection
            start = time.time()
            faces = face_recognizer.detect_faces(frame)
            times['detection'].append(time.time() - start)
            
            # Anti-spoofing
            if faces:
                start = time.time()
                x, y, w, h = faces[0]
                face_color = face_recognizer.extract_face(frame, faces[0], grayscale=False)
                result = anti_spoofing_detector.detect_spoofing(frame, face_color)
                times['spoofing'].append(time.time() - start)
            
            times['total'].append(time.time() - start_total)
            
            if (i + 1) % 10 == 0:
                print(f"  {i + 1}/30 frames traités...")
        
        cap.release()
        
        # Statistiques
        import statistics
        
        print(f"""
✅ Résultats de performance:

Détection faciale:
  Moyenne: {statistics.mean(times['detection'])*1000:.1f}ms
  Min: {min(times['detection'])*1000:.1f}ms
  Max: {max(times['detection'])*1000:.1f}ms
  
Anti-spoofing:
  Moyenne: {statistics.mean(times['spoofing'])*1000:.1f}ms
  Min: {min(times['spoofing'])*1000:.1f}ms
  Max: {max(times['spoofing'])*1000:.1f}ms
  
Total:
  Moyenne: {statistics.mean(times['total'])*1000:.1f}ms
  FPS estimé: {1/statistics.mean(times['total']):.1f}
        """)
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


def main():
    """Menu principal de démonstration."""
    print("\n" + "="*70)
    print(" TEST COMPLET DU SYSTÈME")
    print("="*70)
    print("""
Ce programme teste tous les composants du système
de contrôle d'accès biométrique.

Assurez-vous que:
  ✅ Une caméra est connectée
  ✅ L'environnement est activé
  ✅ Les dépendances sont installées
    """)
    
    demos = {
        '1': ("Détection Faciale", demo_face_detection),
        '2': ("Anti-Spoofing", demo_anti_spoofing),
        '3': ("Reconnaissance Complète", demo_full_recognition),
        '4': ("Base de Données", demo_database),
        '5': ("Test de Performance", demo_performance),
    }
    
    while True:
        print("\n" + "="*60)
        print("MENU DES DÉMOS")
        print("="*60)
        
        for key, (name, _) in demos.items():
            print(f"{key}. {name}")
        print("0. Quitter")
        
        choice = input("\nChoix: ").strip()
        
        if choice == '0':
            print("Au revoir!")
            break
        elif choice in demos:
            try:
                name, func = demos[choice]
                func()
            except KeyboardInterrupt:
                print("\n⏹️  Démonstration arrêtée")
            except Exception as e:
                print(f"\n❌ Erreur: {e}")
        else:
            print("❌ Option invalide")
        
        input("\n[Appuyez sur ENTRÉE pour continuer...]")


if __name__ == '__main__':
    main()
