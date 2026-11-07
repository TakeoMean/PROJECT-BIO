# -*- coding: utf-8 -*-
"""
Module de Reconnaissance Faciale
================================
Détection et reconnaissance de visages utilisant OpenCV et scikit-learn.
Optimisé pour le traitement en temps réel (< 2 secondes).
"""

import cv2
import numpy as np
import os
import pickle
import time
from typing import Optional, Tuple, List, Dict, Any
from datetime import datetime
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import SVC
from sklearn.neighbors import KNeighborsClassifier
import threading
import logging

import config

logger = logging.getLogger(__name__)


class FaceRecognizer:
    """
    Classe de reconnaissance faciale utilisant LBPH, Eigenfaces ou SVM.
    Supporte la détection multi-visages et la robustesse aux variations d'éclairage.
    """

    def __init__(self):
        """Initialise le système de reconnaissance faciale."""
        # Charger le classificateur de cascade Haar
        cascade_path = cv2.data.haarcascades + config.FACE_RECOGNITION['cascade_path']
        self.face_cascade = cv2.CascadeClassifier(cascade_path)
        
        # Recognizer LBPH (Local Binary Patterns Histograms) - robuste à l'éclairage
        self.recognizer = cv2.face.LBPHFaceRecognizer_create(
            radius=1,
            neighbors=8,
            grid_x=8,
            grid_y=8,
            threshold=config.FACE_RECOGNITION['confidence_threshold']
        )
        
        # Classificateur SVM comme backup
        self.svm_classifier = SVC(kernel='linear', probability=True)
        self.knn_classifier = KNeighborsClassifier(n_neighbors=3)
        self.label_encoder = LabelEncoder()
        
        # État du modèle
        self.is_trained = False
        self.known_faces = {}  # {user_id: [face_encodings]}
        self.model_path = os.path.join(config.BASE_DIR, "data", "face_model.yml")
        self.encodings_path = os.path.join(config.BASE_DIR, "data", "face_encodings.pkl")
        
        # Charger le modèle existant si disponible
        self._load_model()
        
        # Paramètres de détection
        self.scale_factor = config.FACE_RECOGNITION['scale_factor']
        self.min_neighbors = config.FACE_RECOGNITION['min_neighbors']
        self.min_face_size = config.FACE_RECOGNITION['min_face_size']
        
        # Performance optimization
        self.frame_counter = 0
        self.frame_skip = config.PERFORMANCE['frame_skip']
        self.resize_scale = config.PERFORMANCE['resize_scale']
        self.cache_enabled = config.PERFORMANCE['cache_enabled']
        self.face_cache = {}
        self.cache_max_age = 5  # Secondes

        # Recognition stability
        self.max_distance = config.FACE_RECOGNITION.get('max_distance', 0.05)
        self.fallback_distance = config.FACE_RECOGNITION.get('fallback_distance', 0.07)
        self.stability_hold_seconds = config.FACE_RECOGNITION.get('stability_hold_seconds', 1.5)
        self.min_stable_confidence = config.FACE_RECOGNITION.get(
            'min_stable_confidence',
            config.FACE_RECOGNITION['confidence_threshold']
        )
        self._last_stable = {
            'user_id': None,
            'confidence': 0.0,
            'timestamp': 0.0
        }
        
        # Short detection lock to prevent repeated alerts but keep UI responsive
        self._detection_lock = {
            'locked': False,
            'lock_time': 0.0,
            'lock_duration': 3  # Reduced from 30 to 3 seconds
        }
        
        # Threading pour traitement asynchrone
        self.threading_enabled = config.PERFORMANCE['threading']
        self.processing_lock = threading.Lock()
        
        # Anti-spoofing
        try:
            from anti_spoofing_module import anti_spoofing_detector
            self.anti_spoofing = anti_spoofing_detector
            self.spoofing_enabled = config.ANTI_SPOOFING['enabled']
        except ImportError:
            logger.warning("Module anti-spoofing non disponible")
            self.spoofing_enabled = False
        
        # Tracking des performances
        self.last_recognition_time = 0
        self.performance_metrics = {'avg_time': 0, 'total_recognitions': 0}
        
        logger.info("Reconnaissance faciale initialisée")

    def _apply_stability(self, best_match: int, best_distance: float, confidence: float) -> Tuple[bool, float]:
        """Applique une stabilisation temporelle pour limiter les oscillations."""
        now = time.time()
        threshold = config.FACE_RECOGNITION['confidence_threshold']

        if confidence >= threshold:
            self._last_stable = {
                'user_id': best_match,
                'confidence': confidence,
                'timestamp': now
            }
            return True, confidence

        if (
            self._last_stable['user_id'] == best_match and
            (now - self._last_stable['timestamp']) <= self.stability_hold_seconds and
            best_distance <= self.fallback_distance and
            self._last_stable['confidence'] >= self.min_stable_confidence
        ):
            stabilized = max(confidence, self._last_stable['confidence'] * 0.9)
            return True, stabilized

        return False, confidence

    def _clear_detection_lock(self):
        """Déverrouille la détection quand un utilisateur connu est reconnu."""
        if self._detection_lock['locked']:
            logger.info("Détection déverrouillée (utilisateur reconnu)")
            self._detection_lock['locked'] = False
            self._detection_lock['lock_time'] = 0.0

    def _load_model(self):
        """Charge le modèle de reconnaissance pré-entraîné."""
        try:
            if os.path.exists(self.model_path):
                self.recognizer.read(self.model_path)
                self.is_trained = True
                print("[INFO] Modèle LBPH chargé avec succès")
            
            if os.path.exists(self.encodings_path):
                with open(self.encodings_path, 'rb') as f:
                    data = pickle.load(f)
                    self.known_faces = data.get('faces', {})
                    if data.get('labels'):
                        self.label_encoder.classes_ = np.array(data['labels'])
                print(f"[INFO] {len(self.known_faces)} utilisateurs chargés")
        except Exception as e:
            print(f"[WARNING] Impossible de charger le modèle: {e}")

    def _save_model(self):
        """Sauvegarde le modèle entraîné."""
        try:
            if self.is_trained:
                self.recognizer.save(self.model_path)
            
            with open(self.encodings_path, 'wb') as f:
                pickle.dump({
                    'faces': self.known_faces,
                    'labels': list(self.label_encoder.classes_) if hasattr(self.label_encoder, 'classes_') else []
                }, f)
            print("[INFO] Modèle sauvegardé avec succès")
        except Exception as e:
            print(f"[ERROR] Impossible de sauvegarder le modèle: {e}")

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Prétraite l'image pour améliorer la détection.
        """
        # OpenCV Haar cascade is already robust; heavy preprocessing (CLAHE, Denoising)
        # can sometimes destroy facial features and make detection fail.
        # We just return the image as-is or with very light equalization if needed.
        return cv2.equalizeHist(image)

    def _adjust_brightness_contrast(self, image: np.ndarray) -> np.ndarray:
        """
        Ajuste automatiquement la luminosité et le contraste.
        
        Args:
            image: Image BGR
            
        Returns:
            Image ajustée
        """
        try:
            # Convertir en LAB pour meilleur contraste
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # Appliquer CLAHE sur le canal L
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            
            # Fusionner et reconvertir
            enhanced = cv2.merge([l, a, b])
            result = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
            
            return result
        except Exception as e:
            logger.warning(f"Erreur ajustement brightness: {e}")
            return image

    def detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Détecte les visages dans une image.
        
        Args:
            frame: Image BGR ou en niveaux de gris
            
        Returns:
            Liste de rectangles (x, y, w, h) pour chaque visage détecté
        """
        # Convertir en niveaux de gris si nécessaire
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        
        # Prétraitement pour améliorer la détection
        gray = self.preprocess_image(gray)
        
        # Détection des visages
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=self.min_face_size,
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        return list(faces)

    def extract_face(self, frame: np.ndarray, face_rect: Tuple[int, int, int, int],
                     size: Tuple[int, int] = (200, 200), grayscale: bool = True) -> np.ndarray:
        """
        Extrait et normalise une région de visage.
        
        Args:
            frame: Image source
            face_rect: Rectangle (x, y, w, h) du visage
            size: Taille de sortie souhaitée
            grayscale: Extraire en niveaux de gris (True) ou en couleur (False)
            
        Returns:
            Image du visage normalisée
        """
        x, y, w, h = face_rect
        
        # Préparer l'image de base
        if grayscale:
            base = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
        else:
            base = frame if len(frame.shape) == 3 else cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        
        # Extraire la région du visage avec une marge
        margin = int(0.1 * w)
        y1 = max(0, y - margin)
        height, width = base.shape[:2]
        y2 = min(height, y + h + margin)
        x1 = max(0, x - margin)
        x2 = min(width, x + w + margin)
        
        face = base[y1:y2, x1:x2]
        
        # Redimensionner à la taille standard
        face_resized = cv2.resize(face, size, interpolation=cv2.INTER_LANCZOS4)
        
        if grayscale:
            # Prétraitement
            return self.preprocess_image(face_resized)

        return face_resized

    def get_face_encoding(self, face_image: np.ndarray) -> np.ndarray:
        """
        Calcule l'encodage d'un visage pour la comparaison.
        Utilise les histogrammes LBP comme descripteur.
        
        Args:
            face_image: Image du visage en niveaux de gris
            
        Returns:
            Vecteur d'encodage du visage
        """
        # Calculer l'histogramme LBP
        radius = 1
        n_points = 8 * radius
        
        # Implémenter LBP manuellement pour l'encodage
        lbp = np.zeros_like(face_image)
        for i in range(radius, face_image.shape[0] - radius):
            for j in range(radius, face_image.shape[1] - radius):
                center = face_image[i, j]
                code = 0
                for k in range(n_points):
                    angle = 2 * np.pi * k / n_points
                    x = i + int(round(radius * np.cos(angle)))
                    y = j + int(round(radius * np.sin(angle)))
                    if face_image[x, y] >= center:
                        code |= (1 << k)
                lbp[i, j] = code
        
        # Calculer l'histogramme
        hist, _ = np.histogram(lbp.ravel(), bins=256, range=(0, 256))
        hist = hist.astype(np.float32)
        hist /= (hist.sum() + 1e-7)  # Normalisation
        
        return hist

    def register_face(self, user_id: int, face_images: List[np.ndarray]) -> bool:
        """
        Enregistre les visages d'un nouvel utilisateur.
        
        Args:
            user_id: ID de l'utilisateur
            face_images: Liste d'images de visages
            
        Returns:
            True si l'enregistrement a réussi
        """
        try:
            encodings = []
            for img in face_images:
                # Détecter le visage si l'image n'est pas déjà un visage extrait
                if img.shape[0] > 300 or img.shape[1] > 300:
                    faces = self.detect_faces(img)
                    if faces:
                        face = self.extract_face(img, faces[0])
                    else:
                        continue
                else:
                    face = img if len(img.shape) == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    face = cv2.resize(face, (200, 200))
                
                encoding = self.get_face_encoding(face)
                encodings.append(encoding)
            
            if encodings:
                self.known_faces[user_id] = encodings
                self._retrain_model()
                return True
            return False
            
        except Exception as e:
            print(f"[ERROR] Erreur lors de l'enregistrement: {e}")
            return False

    def _retrain_model(self):
        """Réentraîne le modèle avec toutes les données connues."""
        if not self.known_faces:
            return
        
        faces = []
        labels = []
        
        for user_id, encodings in self.known_faces.items():
            for _ in encodings:
                # Pour LBPH, on a besoin des images originales
                # On utilise les encodings pour le classificateur backup
                labels.append(user_id)
        
        if labels:
            # Entraîner le classificateur SVM avec les encodings
            all_encodings = []
            all_labels = []
            for user_id, encodings in self.known_faces.items():
                for enc in encodings:
                    all_encodings.append(enc)
                    all_labels.append(user_id)
            
            if len(set(all_labels)) > 1:
                X = np.array(all_encodings)
                y = np.array(all_labels)
                self.label_encoder.fit(y)
                self.svm_classifier.fit(X, y)
                self.knn_classifier.fit(X, y)
            
            self.is_trained = True
            self._save_model()

    def train_from_database(self, users_data: List[Dict]) -> bool:
        """
        Entraîne le modèle à partir des données de la base de données.
        
        Args:
            users_data: Liste des utilisateurs avec leurs encodages faciaux
            
        Returns:
            True si l'entraînement a réussi
        """
        try:
            faces = []
            labels = []
            
            for user in users_data:
                if user.get('face_encoding'):
                    # Désérialiser l'encodage
                    encoding_data = pickle.loads(user['face_encoding'])
                    if isinstance(encoding_data, list):
                        self.known_faces[user['id']] = encoding_data
                        for enc in encoding_data:
                            faces.append(enc)
                            labels.append(user['id'])
            
            if faces and len(set(labels)) > 1:
                X = np.array(faces)
                y = np.array(labels)
                self.label_encoder.fit(y)
                self.svm_classifier.fit(X, y)
                self.knn_classifier.fit(X, y)
                self.is_trained = True
                self._save_model()
                return True
            elif faces:
                self.is_trained = True
                return True
            
            return False
            
        except Exception as e:
            print(f"[ERROR] Erreur lors de l'entraînement: {e}")
            return False

    def recognize(self, frame: np.ndarray, timeout: float = None) -> List[Dict]:
        """
        Reconnaît les visages dans une image avec anti-spoofing.
        
        Args:
            frame: Image BGR
            timeout: Temps maximum pour la reconnaissance (en secondes)
            
        Returns:
            Liste de dictionnaires avec les résultats incluant anti-spoofing:
            {
                'user_id': int ou None,
                'confidence': float,
                'face_rect': (x, y, w, h),
                'recognized': bool,
                'is_real': bool,
                'spoofing_confidence': float,
                'spoofing_details': dict
            }
        """
        start_time = time.time()
        timeout = timeout or config.FACE_RECOGNITION['recognition_timeout']
        results = []
        
        try:
            # Optimization: skip frames - use cached result if available
            self.frame_counter += 1
            if self.frame_counter % self.frame_skip != 0:
                # Return last known results (keeps bounding boxes on screen)
                return self._last_frame_results if hasattr(self, '_last_frame_results') else results
            
            # Optimization: resize frame for faster processing
            if self.resize_scale < 1.0:
                h, w = frame.shape[:2]
                new_w, new_h = int(w * self.resize_scale), int(h * self.resize_scale)
                frame_resized = cv2.resize(frame, (new_w, new_h))
            else:
                frame_resized = frame
            
            # Détecter les visages
            faces = self.detect_faces(frame_resized)
            
            if not faces:
                return results
            
            # Handle multiple faces
            multi_face_mode = config.FLEXIBILITY['multi_face_handling']
            if multi_face_mode == 'largest':
                faces = [max(faces, key=lambda f: f[2] * f[3])]
            elif multi_face_mode == 'closest':
                faces = [min(faces, key=lambda f: abs(f[0] + f[2]/2 - frame_resized.shape[1]/2) + 
                                              abs(f[1] + f[3]/2 - frame_resized.shape[0]/2))]
            
            for face_rect in faces:
                if time.time() - start_time > timeout:
                    logger.warning("Timeout de reconnaissance atteint")
                    break
                
                try:
                    # Échelle la face rectangle aux dimensions originales si redimensionné
                    if self.resize_scale < 1.0:
                        scaled_rect = tuple(int(x / self.resize_scale) for x in face_rect)
                    else:
                        scaled_rect = face_rect
                    
                    # Extraire le visage (couleur pour anti-spoofing, gris pour reconnaissance)
                    face_color = self.extract_face(frame, scaled_rect, grayscale=False)
                    face = self.extract_face(frame, scaled_rect)
                    
                    result = {
                        'user_id': None,
                        'confidence': 0.0,
                        'face_rect': scaled_rect,
                        'recognized': False,
                        'is_real': True,  # Default assume real
                        'spoofing_confidence': 1.0,
                        'spoofing_details': {}
                    }
                    
                    # Anti-spoofing detection
                    if self.spoofing_enabled:
                        spoofing_result = self.anti_spoofing.detect_spoofing(frame, face_color)
                        result['is_real'] = spoofing_result['is_real']
                        result['spoofing_confidence'] = spoofing_result['confidence']
                        result['spoofing_details'] = spoofing_result['details']
                        
                        if not spoofing_result['is_real']:
                            logger.warning(f"Usurpation détectée: {spoofing_result['confidence']:.2%}")
                            self._last_stable['user_id'] = None
                            results.append(result)
                            continue
                    
                    # Reconnaissance faciale
                    encoding = self.get_face_encoding(face)
                    
                    if self.is_trained and self.known_faces:
                        best_match = None
                        best_distance = float('inf')
                        
                        # Reconnaissance avec gestion d'erreur
                        try:
                            for user_id, user_encodings in self.known_faces.items():
                                for user_enc in user_encodings:
                                    distance = np.linalg.norm(encoding - user_enc)
                                    if distance < best_distance:
                                        best_distance = distance
                                        best_match = user_id
                            
                            if best_match is not None and best_distance < self.max_distance:
                                confidence = 100 * (1 - (best_distance / self.max_distance))
                                confidence = max(0, min(100, confidence))

                                recognized, confidence = self._apply_stability(
                                    best_match, best_distance, confidence
                                )

                                if recognized:
                                    result['user_id'] = int(best_match)
                                    result['confidence'] = confidence
                                    result['recognized'] = True
                                    # Clear the detection lock for authorized users
                                    self._clear_detection_lock()
                                else:
                                    result['confidence'] = confidence
                            else:
                                # Unknown/unauthorized face detected - lock detection for 30 seconds
                                if best_distance < float('inf'):
                                    confidence = max(0, 100 * (1 - (best_distance / (self.max_distance * 1.2))))
                                    result['confidence'] = confidence
                                
                        except Exception as e:
                            if config.FLEXIBILITY['recover_on_error']:
                                logger.error(f"Erreur reconnaissance (récupération): {e}")
                                result['recognized'] = False
                            else:
                                raise
                    
                    results.append(result)
                    
                except Exception as e:
                    if config.FLEXIBILITY['recover_on_error']:
                        logger.error(f"Erreur traitement face (récupération): {e}")
                        continue
                    else:
                        raise
            
            # Log performance metrics
            elapsed = time.time() - start_time
            self.performance_metrics['total_recognitions'] += 1
            self.performance_metrics['avg_time'] = (
                (self.performance_metrics['avg_time'] * (self.performance_metrics['total_recognitions'] - 1) + elapsed) /
                self.performance_metrics['total_recognitions']
            )
            
            if config.LOGGING['performance_monitoring']:
                logger.debug(f"Reconnaissance en {elapsed:.3f}s (moyenne: {self.performance_metrics['avg_time']:.3f}s)")
            
            # Cache results for skipped frames
            if results:
                self._last_frame_results = results
            return results
            
        except Exception as e:
            logger.error(f"Erreur critique dans recognize: {e}")
            if config.FLEXIBILITY['degraded_mode']:
                logger.warning("Mode dégradé activé")
                return results
            else:
                raise

    def capture_training_images(self, camera, num_images: int = None,
                                callback=None) -> List[np.ndarray]:
        """
        Capture des images d'entraînement à partir de la caméra.
        
        Args:
            camera: Objet caméra OpenCV (ou index)
            num_images: Nombre d'images à capturer
            callback: Fonction de callback pour l'interface (progress, frame)
            
        Returns:
            Liste des images de visages capturées
        """
        num_images = num_images or config.FACE_RECOGNITION['training_images_per_user']
        
        if isinstance(camera, int):
            cap = cv2.VideoCapture(camera)
        else:
            cap = camera
        
        captured_faces = []
        attempts = 0
        max_attempts = num_images * 10  # Maximum de tentatives
        
        while len(captured_faces) < num_images and attempts < max_attempts:
            ret, frame = cap.read()
            if not ret:
                attempts += 1
                continue
            
            faces = self.detect_faces(frame)
            
            if len(faces) == 1:  # Un seul visage détecté
                face = self.extract_face(frame, faces[0])
                captured_faces.append(face)
                
                # Dessiner le rectangle et le compteur
                x, y, w, h = faces[0]
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                cv2.putText(frame, f"Capture: {len(captured_faces)}/{num_images}",
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                if callback:
                    callback(len(captured_faces) / num_images, frame)
                
                # Petite pause entre les captures
                cv2.waitKey(200)
            
            elif len(faces) > 1:
                cv2.putText(frame, "Plusieurs visages detectes!",
                           (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                if callback:
                    callback(len(captured_faces) / num_images, frame)
            
            attempts += 1
        
        if isinstance(camera, int):
            cap.release()
        
        return captured_faces

    def save_face_encoding_for_db(self, face_images: List[np.ndarray]) -> bytes:
        """
        Prépare les encodages de visages pour le stockage en base de données.
        
        Args:
            face_images: Liste d'images de visages
            
        Returns:
            Données sérialisées pour la base de données
        """
        encodings = []
        for img in face_images:
            if img.shape[0] != 200 or img.shape[1] != 200:
                img = cv2.resize(img, (200, 200))
            if len(img.shape) == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            encoding = self.get_face_encoding(img)
            encodings.append(encoding)
        
        return pickle.dumps(encodings)

    def draw_results(self, frame: np.ndarray, results: List[Dict],
                     users_info: Dict[int, str] = None) -> np.ndarray:
        """
        Dessine les résultats de reconnaissance sur l'image.
        
        Args:
            frame: Image source
            results: Résultats de la reconnaissance
            users_info: Dictionnaire {user_id: nom} pour afficher les noms
            
        Returns:
            Image avec les annotations
        """
        frame_copy = frame.copy()
        
        for result in results:
            x, y, w, h = result['face_rect']
            
            if result['recognized']:
                color = (0, 255, 0)  # Vert pour reconnu
                user_name = users_info.get(result['user_id'], f"ID: {result['user_id']}") if users_info else f"ID: {result['user_id']}"
                label = f"{user_name} ({result['confidence']:.1f}%)"
            else:
                color = (0, 0, 255)  # Rouge pour non reconnu
                label = "Inconnu"
            
            # Dessiner le rectangle
            cv2.rectangle(frame_copy, (x, y), (x+w, y+h), color, 2)
            
            # Dessiner le label
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
            cv2.rectangle(frame_copy, (x, y - label_size[1] - 10),
                         (x + label_size[0], y), color, -1)
            cv2.putText(frame_copy, label, (x, y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return frame_copy

    def save_capture(self, frame: np.ndarray, face_rect: Tuple[int, int, int, int] = None,
                     prefix: str = "capture") -> str:
        """
        Sauvegarde une capture d'image pour les logs.
        
        Args:
            frame: Image à sauvegarder
            face_rect: Rectangle du visage (optionnel)
            prefix: Préfixe du nom de fichier
            
        Returns:
            Chemin du fichier sauvegardé
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{prefix}_{timestamp}.jpg"
        filepath = os.path.join(config.CAPTURES_DIR, filename)
        
        # Si un rectangle est fourni, dessiner le cadre
        if face_rect is not None:
            frame_copy = frame.copy()
            x, y, w, h = face_rect
            cv2.rectangle(frame_copy, (x, y), (x+w, y+h), (0, 0, 255), 3)
            cv2.imwrite(filepath, frame_copy)
        else:
            cv2.imwrite(filepath, frame)
        
        return filepath


# Instance globale
face_recognizer = FaceRecognizer()
