# -*- coding: utf-8 -*-
"""
Script de Validation et Test
============================
Valide le système: détection faciale, anti-spoofing, et reconnaissance.
"""

import cv2
import numpy as np
import os
from typing import List, Dict, Tuple
import sys

import config
from face_recognition_module import face_recognizer
from anti_spoofing_module import anti_spoofing_detector
from database import db_manager


class SystemValidator:
    """Valide et teste tous les composants du système."""

    def __init__(self):
        """Initialise le validateur."""
        self.results = {
            'face_detection': [],
            'anti_spoofing': [],
            'recognition': [],
            'overall': True
        }

    def test_camera(self, camera_index: int = 0, num_frames: int = 5) -> bool:
        """Teste l'accès à la caméra."""
        print("\n" + "="*60)
        print("TEST 1: CAMÉRA")
        print("="*60)
        
        try:
            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                print("❌ Impossible d'ouvrir la caméra")
                return False
            
            for i in range(num_frames):
                ret, frame = cap.read()
                if not ret:
                    print(f"❌ Erreur lecture frame {i+1}")
                    cap.release()
                    return False
                
                h, w = frame.shape[:2]
                print(f"✅ Frame {i+1}: {w}x{h}")
            
            cap.release()
            print("✅ Caméra fonctionnelle")
            return True
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return False

    def test_face_detection(self, camera_index: int = 0, timeout: int = 30) -> bool:
        """Teste la détection faciale."""
        print("\n" + "="*60)
        print("TEST 2: DÉTECTION FACIALE")
        print("="*60)
        
        try:
            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                print("❌ Caméra indisponible")
                return False
            
            print(f"En attente d'un visage... (timeout: {timeout}s)")
            import time
            start = time.time()
            
            while time.time() - start < timeout:
                ret, frame = cap.read()
                if not ret:
                    continue
                
                faces = face_recognizer.detect_faces(frame)
                
                if faces:
                    print(f"✅ {len(faces)} visage(s) détecté(s)")
                    for i, (x, y, w, h) in enumerate(faces):
                        print(f"   Face {i+1}: position ({x}, {y}), taille {w}x{h}")
                    cap.release()
                    return True
                
                # Afficher le frame
                cv2.imshow("Détection faciale - Positionnez-vous", frame)
                if cv2.waitKey(1) & 0xFF == 27:  # ESC
                    break
            
            cap.release()
            cv2.destroyAllWindows()
            print("❌ Aucun visage détecté")
            return False
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return False

    def test_anti_spoofing(self, camera_index: int = 0, timeout: int = 30) -> bool:
        """Teste la détection anti-spoofing."""
        print("\n" + "="*60)
        print("TEST 3: ANTI-SPOOFING")
        print("="*60)
        
        try:
            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                print("❌ Caméra indisponible")
                return False
            
            print(f"En attente d'un visage... (timeout: {timeout}s)")
            print("Test réel vs présentation photo/écran")
            import time
            start = time.time()
            
            while time.time() - start < timeout:
                ret, frame = cap.read()
                if not ret:
                    continue
                
                faces = face_recognizer.detect_faces(frame)
                
                if faces:
                    x, y, w, h = faces[0]
                    face_color = face_recognizer.extract_face(frame, faces[0], grayscale=False)
                    
                    # Test anti-spoofing
                    result = anti_spoofing_detector.detect_spoofing(frame, face_color)
                    
                    print(f"\n✅ Résultat Anti-Spoofing:")
                    print(f"   Réel: {'OUI' if result['is_real'] else 'NON'}")
                    print(f"   Confiance: {result['confidence']:.2%}")
                    print(f"   Méthode: {result['method']}")
                    print(f"   Détails:")
                    for key, val in result.get('details', {}).items():
                        if isinstance(val, (int, float)):
                            print(f"     - {key}: {val:.3f}")
                    
                    # Afficher l'analyse
                    cv2.imshow("Anti-Spoofing", frame)
                    if cv2.waitKey(1) & 0xFF == 27:  # ESC
                        break
                    
                    cap.release()
                    cv2.destroyAllWindows()
                    return True
                
                # Afficher le frame
                cv2.imshow("Anti-Spoofing - Positionnez-vous", frame)
                if cv2.waitKey(1) & 0xFF == 27:  # ESC
                    break
            
            cap.release()
            cv2.destroyAllWindows()
            print("❌ Aucun visage détecté")
            return False
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return False

    def test_database(self) -> bool:
        """Teste la base de données."""
        print("\n" + "="*60)
        print("TEST 4: BASE DE DONNÉES")
        print("="*60)
        
        try:
            # Compter les utilisateurs
            users = db_manager.get_all_users()
            print(f"✅ Utilisateurs: {len(users)}")
            
            # Compter les zones
            zones = db_manager.get_zones()
            print(f"✅ Zones: {len(zones)}")
            
            # Compter les logs
            logs = db_manager.get_access_logs(limit=10)
            print(f"✅ Logs d'accès: {len(logs)} (derniers)")
            
            print("✅ Base de données fonctionnelle")
            return True
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return False

    def test_training_data(self) -> bool:
        """Teste les données d'entraînement."""
        print("\n" + "="*60)
        print("TEST 5: DONNÉES D'ENTRAÎNEMENT")
        print("="*60)
        
        try:
            faces_dir = config.FACES_DIR
            
            if not os.path.exists(faces_dir):
                print("⚠️  Dossier de visages non trouvé")
                return False
            
            total_images = 0
            user_count = 0
            
            for user_folder in os.listdir(faces_dir):
                user_path = os.path.join(faces_dir, user_folder)
                if os.path.isdir(user_path):
                    images = len([f for f in os.listdir(user_path) if f.endswith('.jpg')])
                    if images > 0:
                        user_count += 1
                        total_images += images
                        status = "✅" if images >= 60 else "⚠️"
                        print(f"{status} {user_folder}: {images} images")
            
            print(f"\n📊 Total: {total_images} images pour {user_count} utilisateurs")
            
            if total_images >= 300:
                print("✅ Dataset complet (≥ 300 images)")
                return True
            elif total_images > 0:
                print(f"⚠️  Dataset partiel ({total_images}/300 images)")
                print("   Exécutez training_data_generator.py pour capturer plus d'images")
                return True
            else:
                print("❌ Aucune donnée d'entraînement trouvée")
                return False
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return False

    def test_recognition_model(self) -> bool:
        """Teste le modèle de reconnaissance."""
        print("\n" + "="*60)
        print("TEST 6: MODÈLE DE RECONNAISSANCE")
        print("="*60)
        
        try:
            if not face_recognizer.is_trained:
                print("⚠️  Modèle non entraîné")
                print("   Exécutez init_advanced.py pour entraîner le modèle")
                return False
            
            known_count = len(face_recognizer.known_faces)
            print(f"✅ Modèle entraîné avec {known_count} utilisateurs")
            
            if known_count > 0:
                print("✅ Modèle prêt pour reconnaissance")
                return True
            else:
                print("⚠️  Modèle sans utilisateurs")
                return True
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            return False

    def run_all_tests(self, camera_index: int = 0) -> Dict:
        """Exécute tous les tests."""
        print("\n" + "="*70)
        print(" VALIDATION COMPLÈTE DU SYSTÈME")
        print("="*70)
        print(f"Base de données: {config.DATABASE_PATH}")
        print(f"Images: {config.FACES_DIR}")
        print("="*70)
        
        tests = [
            ("Caméra", lambda: self.test_camera(camera_index)),
            ("Détection faciale", lambda: self.test_face_detection(camera_index)),
            ("Anti-spoofing", lambda: self.test_anti_spoofing(camera_index)),
            ("Base de données", self.test_database),
            ("Données d'entraînement", self.test_training_data),
            ("Modèle de reconnaissance", self.test_recognition_model),
        ]
        
        results = {}
        for test_name, test_func in tests:
            try:
                result = test_func()
                results[test_name] = result
            except KeyboardInterrupt:
                print("\n⚠️  Test interrompu par l'utilisateur")
                results[test_name] = False
            except Exception as e:
                print(f"\n❌ Erreur non gérée: {e}")
                results[test_name] = False
        
        # Résumé
        print("\n" + "="*70)
        print(" RÉSUMÉ DES TESTS")
        print("="*70)
        
        passed = sum(1 for v in results.values() if v)
        total = len(results)
        
        for test_name, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{status}: {test_name}")
        
        print(f"\nTotal: {passed}/{total} tests réussis")
        
        if passed == total:
            print("\n🎉 SYSTÈME COMPLÈTEMENT OPÉRATIONNEL")
        elif passed >= total - 1:
            print("\n⚠️  SYSTÈME PARTIELLEMENT OPÉRATIONNEL")
            print("   Quelques ajustements nécessaires")
        else:
            print("\n❌ SYSTÈME NON PRÊT")
            print("   Corriger les erreurs avant utilisation")
        
        print("="*70 + "\n")
        
        return results


def main():
    """Fonction principale."""
    validator = SystemValidator()
    validator.run_all_tests()


if __name__ == '__main__':
    main()
