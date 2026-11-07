# -*- coding: utf-8 -*-
"""
Générateur de Données d'Entraînement
====================================
Génère 300 images de visages d'entraînement à partir de la caméra ou de fichiers.
"""

import cv2
import numpy as np
import os
import sys
from typing import List, Tuple
from datetime import datetime
import json

import config
from face_recognition_module import face_recognizer


class TrainingDataGenerator:
    """Génère des données d'entraînement pour la reconnaissance faciale."""

    def __init__(self):
        """Initialise le générateur."""
        self.faces_dir = config.FACES_DIR
        os.makedirs(self.faces_dir, exist_ok=True)

    def capture_training_set(self, user_id: int, user_name: str, 
                           num_images: int = 300, camera_index: int = 0) -> bool:
        """
        Capture un ensemble de données d'entraînement pour un utilisateur.
        
        Args:
            user_id: ID de l'utilisateur
            user_name: Nom de l'utilisateur
            num_images: Nombre d'images à capturer (défaut 300)
            camera_index: Index de la caméra
            
        Returns:
            True si le capture a réussi
        """
        print(f"\n{'='*60}")
        print(f"Capture d'entraînement pour {user_name} ({user_id})")
        print(f"{'='*60}")
        print(f"\nCapture de {num_images} images...")
        print("Instructions:")
        print("1. Positionnez votre visage devant la caméra")
        print("2. Bougez légèrement votre tête (haut, bas, droite, gauche)")
        print("3. Variez l'éclairage si possible")
        print("4. Pressez 'ESC' pour arrêter, 'SPACE' pour passer une image\n")

        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            print("❌ Erreur: Impossible d'ouvrir la caméra!")
            return False

        # Créer le dossier utilisateur
        user_dir = os.path.join(self.faces_dir, f"user_{user_id}_{user_name}")
        os.makedirs(user_dir, exist_ok=True)

        captured_faces = []
        attempts = 0
        max_attempts = num_images * 15  # Maximum de tentatives

        while len(captured_faces) < num_images and attempts < max_attempts:
            ret, frame = cap.read()
            if not ret:
                attempts += 1
                continue

            # Détecter les visages
            faces = face_recognizer.detect_faces(frame)

            if len(faces) == 1:
                # Extraire le visage
                x, y, w, h = faces[0]
                face = face_recognizer.extract_face(frame, faces[0])
                
                # Appliquer des augmentations légères pour plus de variabilité
                face_augmented = self._augment_face(face)
                captured_faces.append(face_augmented)
                
                # Sauvegarder l'image
                filename = os.path.join(user_dir, f"face_{len(captured_faces):04d}.jpg")
                cv2.imwrite(filename, face)
                
                # Affichage
                display_frame = frame.copy()
                cv2.rectangle(display_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(display_frame, f"Capture: {len(captured_faces)}/{num_images}",
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.putText(display_frame, "SPACE: skip, ESC: quit",
                           (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 1)
                
                cv2.imshow("Capture Entraînement", display_frame)
                
                key = cv2.waitKey(100) & 0xFF
                if key == 27:  # ESC
                    break
                elif key == 32:  # SPACE
                    attempts += 1
                    continue

            else:
                # Affichage avec instruction
                display_frame = frame.copy()
                if len(faces) > 1:
                    cv2.putText(display_frame, f"Plusieurs visages ({len(faces)}) - SVP un seul",
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                else:
                    cv2.putText(display_frame, "Aucun visage détecté",
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.imshow("Capture Entraînement", display_frame)
                cv2.waitKey(100)

            attempts += 1

        cap.release()
        cv2.destroyAllWindows()

        if len(captured_faces) >= num_images:
            print(f"\n✅ Succès! {len(captured_faces)} images capturées")
            self._save_metadata(user_id, user_name, user_dir, len(captured_faces))
            return True
        else:
            print(f"\n⚠️  Capture partielle: {len(captured_faces)}/{num_images} images")
            if len(captured_faces) > 0:
                self._save_metadata(user_id, user_name, user_dir, len(captured_faces))
                return True
            else:
                print("❌ Aucune image capturée!")
                return False

    def _augment_face(self, face: np.ndarray) -> np.ndarray:
        """
        Applique des augmentations d'image légères.
        
        Args:
            face: Image du visage
            
        Returns:
            Image augmentée
        """
        augmented = face.copy()
        
        # Rotation légère aléatoire (-5 à 5 degrés)
        if np.random.rand() > 0.5:
            angle = np.random.uniform(-5, 5)
            h, w = augmented.shape[:2]
            M = cv2.getRotationMatrix2D((w/2, h/2), angle, 1)
            augmented = cv2.warpAffine(augmented, M, (w, h))
        
        # Légère variation de luminosité
        if np.random.rand() > 0.5:
            alpha = np.random.uniform(0.8, 1.2)
            augmented = cv2.convertScaleAbs(augmented, alpha=alpha, beta=0)
        
        return augmented

    def _save_metadata(self, user_id: int, user_name: str, user_dir: str, num_captured: int):
        """Sauvegarde les métadonnées d'entraînement."""
        metadata = {
            'user_id': user_id,
            'user_name': user_name,
            'num_images': num_captured,
            'capture_date': datetime.now().isoformat(),
            'directory': user_dir
        }
        
        metadata_path = os.path.join(user_dir, 'metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

    def load_all_training_data(self) -> Tuple[List[np.ndarray], List[int], dict]:
        """
        Charge toutes les données d'entraînement depuis les dossiers.
        
        Returns:
            Tuple (images, labels, metadata)
        """
        images = []
        labels = []
        metadata = {}
        
        if not os.path.exists(self.faces_dir):
            print("❌ Dossier de visages non trouvé!")
            return images, labels, metadata

        for user_folder in os.listdir(self.faces_dir):
            user_path = os.path.join(self.faces_dir, user_folder)
            if not os.path.isdir(user_path):
                continue

            # Extraire l'ID utilisateur
            try:
                user_id = int(user_folder.split('_')[1])
            except (ValueError, IndexError):
                continue

            # Charger les images
            for filename in os.listdir(user_path):
                if filename.endswith('.jpg'):
                    filepath = os.path.join(user_path, filename)
                    img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        images.append(img)
                        labels.append(user_id)

            metadata[user_id] = user_folder

        print(f"✅ Chargé {len(images)} images d'entraînement pour {len(set(labels))} utilisateurs")
        return images, labels, metadata

    def generate_synthetic_dataset(self, num_users: int = 5, images_per_user: int = 60) -> bool:
        """
        Génère un dataset synthétique pour les tests.
        Utile pour le développement sans capture de caméra.
        
        Args:
            num_users: Nombre d'utilisateurs fictifs
            images_per_user: Images par utilisateur
            
        Returns:
            True si succès
        """
        print(f"\n{'='*60}")
        print(f"Génération de dataset synthétique")
        print(f"{num_users} utilisateurs x {images_per_user} images = {num_users * images_per_user} images")
        print(f"{'='*60}\n")

        for user_id in range(1, num_users + 1):
            user_name = f"User_{user_id}"
            user_dir = os.path.join(self.faces_dir, f"user_{user_id}_{user_name}")
            os.makedirs(user_dir, exist_ok=True)

            # Générer des images synthétiques
            for img_idx in range(images_per_user):
                # Créer une image avec du bruit et des patterns
                img = np.random.randint(50, 200, (200, 200), dtype=np.uint8)
                
                # Ajouter un rectangle pour simuler un visage
                x, y = np.random.randint(20, 120), np.random.randint(20, 120)
                cv2.rectangle(img, (x, y), (x+100, y+100), np.random.randint(100, 255), -1)
                
                # Ajouter du bruit gaussien
                noise = np.random.normal(0, 10, img.shape).astype(np.uint8)
                img = cv2.add(img, noise)
                
                # Sauvegarder
                filename = os.path.join(user_dir, f"face_{img_idx+1:04d}.jpg")
                cv2.imwrite(filename, img)
                
                if (img_idx + 1) % 10 == 0:
                    print(f"  {user_name}: {img_idx + 1}/{images_per_user} images générées")

            self._save_metadata(user_id, user_name, user_dir, images_per_user)
            print(f"✅ {user_name}: {images_per_user} images synthétiques générées")

        return True


def main():
    """Menu principal du générateur de données."""
    generator = TrainingDataGenerator()

    while True:
        print("\n" + "="*60)
        print("GÉNÉRATEUR DE DONNÉES D'ENTRAÎNEMENT")
        print("="*60)
        print("\n1. Capturer un nouvel utilisateur (300 images)")
        print("2. Charger et afficher les données existantes")
        print("3. Générer un dataset synthétique (TEST)")
        print("0. Quitter")
        
        choice = input("\nVotre choix: ").strip()
        
        if choice == '0':
            print("Au revoir!")
            break
        elif choice == '1':
            user_id = input("ID utilisateur: ").strip()
            user_name = input("Nom utilisateur: ").strip()
            num_images = input("Nombre d'images (défaut 300): ").strip()
            
            try:
                user_id = int(user_id)
                num_images = int(num_images) if num_images else 300
            except ValueError:
                print("❌ Valeurs invalides!")
                continue
            
            if generator.capture_training_set(user_id, user_name, num_images):
                print("✅ Capture réussie!")
            else:
                print("❌ Capture échouée!")
                
        elif choice == '2':
            images, labels, metadata = generator.load_all_training_data()
            print(f"\n📊 Statistiques:")
            print(f"  Total images: {len(images)}")
            print(f"  Utilisateurs: {len(set(labels))}")
            if metadata:
                for user_id, folder in metadata.items():
                    print(f"  - {folder}: {labels.count(user_id)} images")
                    
        elif choice == '3':
            num_users = input("Nombre d'utilisateurs (défaut 5): ").strip()
            images_per_user = input("Images par utilisateur (défaut 60): ").strip()
            
            try:
                num_users = int(num_users) if num_users else 5
                images_per_user = int(images_per_user) if images_per_user else 60
            except ValueError:
                print("❌ Valeurs invalides!")
                continue
            
            if generator.generate_synthetic_dataset(num_users, images_per_user):
                print("✅ Dataset synthétique généré!")
        else:
            print("❌ Option invalide!")


if __name__ == '__main__':
    main()
