# -*- coding: utf-8 -*-
"""
Module d'Anti-Usurpation (Anti-Spoofing)
=========================================
Détecte si un visage est réel ou présenté via une photo/vidéo.
Utilise plusieurs techniques: texture, couleur, domaine fréquentiel et mouvement.
"""

import cv2
import numpy as np
from typing import Dict, Tuple, Optional, List
import config
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AntiSpoofingDetector:
    """Classe pour la détection d'usurpation par présentation de visage."""

    def __init__(self):
        """Initialise le détecteur anti-spoofing."""
        self.motion_buffer = []
        self.max_buffer_size = 10
        self.last_gray = None
        
    def detect_spoofing(self, frame: np.ndarray, face_region: Optional[np.ndarray] = None) -> Dict:
        """
        Analyse un frame pour détecter l'usurpation.
        Utilise plusieurs méthodes et combine les résultats.
        
        Args:
            frame: Image BGR du frame
            face_region: Région du visage extraite (optionnel)
            
        Returns:
            Dict avec les résultats et le score de vivacité
        """
        if not config.ANTI_SPOOFING['enabled']:
            return {'is_real': True, 'confidence': 1.0, 'method': 'disabled', 'details': {}}
        
        # Validation des images d'entrée
        if frame is None or frame.size == 0:
            return {'is_real': True, 'confidence': 0.5, 'method': 'invalid_frame', 'details': {}}
        
        if face_region is not None and (face_region is None or face_region.size == 0):
            return {'is_real': True, 'confidence': 0.5, 'method': 'invalid_face', 'details': {}}
        
        try:
            results = {}
            scores = {}
            
            # Texture Analysis
            if config.ANTI_SPOOFING['texture']['enabled']:
                scores['texture'] = self._detect_texture(face_region if face_region is not None else frame)
            
            # Color Space Analysis
            if config.ANTI_SPOOFING['color']['enabled']:
                scores['color'] = self._detect_color_spoofing(face_region if face_region is not None else frame)
            
            # Frequency Domain Analysis
            if config.ANTI_SPOOFING['frequency']['enabled']:
                scores['frequency'] = self._detect_frequency_spoofing(face_region if face_region is not None else frame)

            # Screen Glare Detection
            if config.ANTI_SPOOFING['glare']['enabled']:
                glare_source = face_region if face_region is not None else frame
                scores['glare'] = self._detect_screen_glare(glare_source)
                glare_ratio = None
                if len(glare_source.shape) == 3:
                    hsv = cv2.cvtColor(glare_source, cv2.COLOR_BGR2HSV)
                    v = hsv[..., 2].astype(np.float32) / 255.0
                    s = hsv[..., 1].astype(np.float32) / 255.0
                    glare_mask = (v >= config.ANTI_SPOOFING['glare']['v_threshold']) & (
                        s <= config.ANTI_SPOOFING['glare']['s_threshold']
                    )
                    glare_ratio = float(np.mean(glare_mask))
                if glare_ratio is not None:
                    scores['glare_ratio'] = glare_ratio
                    if glare_ratio >= config.ANTI_SPOOFING['glare']['hard_ratio']:
                        return {
                            'is_real': False,
                            'confidence': 0.0,
                            'method': 'glare_hard_block',
                            'details': {'glare_ratio': glare_ratio},
                            'timestamp': datetime.now().isoformat()
                        }
            
            # Motion Detection
            if config.ANTI_SPOOFING['motion']['enabled']:
                motion_source = face_region if face_region is not None else frame
                gray = cv2.cvtColor(motion_source, cv2.COLOR_BGR2GRAY) if len(motion_source.shape) == 3 else motion_source
                motion_score = self._detect_motion(gray)
                if motion_score is None:
                    # Not enough frames; don't fail immediately, just assign a default neutral score (e.g. 0.5) 
                    # or drop motion requirement until buffer is full. Here we give it threshold + 0.05 to pass
                    # temporarily until actual motion check starts. This prevents the immediate impostor block.
                    scores['motion'] = config.ANTI_SPOOFING['motion']['threshold'] + 0.05
                else:
                    scores['motion'] = motion_score
            
            # Screen Pattern Detection (Enhanced phone/tablet detection)
            screen_source = face_region if face_region is not None else frame
            scores['screen_patterns'] = self._detect_screen_patterns(screen_source)
            
            # Combiner les scores avec pondération
            final_score = self._combine_scores(scores)
            confidence = final_score

            # Blocage si texture et fréquence sont faibles (typique photo/écran)
            if config.ANTI_SPOOFING.get('block_on_low_texture_and_frequency', False):
                texture_score = scores.get('texture')
                frequency_score = scores.get('frequency')
                if (
                    isinstance(texture_score, (int, float)) and
                    isinstance(frequency_score, (int, float)) and
                    texture_score <= config.ANTI_SPOOFING['texture']['threshold'] and
                    frequency_score <= config.ANTI_SPOOFING['frequency']['threshold']
                ):
                    return {
                        'is_real': False,
                        'confidence': 0.0,
                        'method': 'low_texture_frequency_block',
                        'details': {'texture': texture_score, 'frequency': frequency_score},
                        'timestamp': datetime.now().isoformat()
                    }

            # Exiger plusieurs méthodes positives pour éviter les faux positifs
            passed = 0
            if config.ANTI_SPOOFING['texture']['enabled']:
                if scores.get('texture', 0) > config.ANTI_SPOOFING['texture']['threshold']:
                    passed += 1
            if config.ANTI_SPOOFING['color']['enabled']:
                if scores.get('color', 0) > config.ANTI_SPOOFING['color']['threshold']:
                    passed += 1
            if config.ANTI_SPOOFING['frequency']['enabled']:
                if scores.get('frequency', 0) > config.ANTI_SPOOFING['frequency']['threshold']:
                    passed += 1
            if config.ANTI_SPOOFING['motion']['enabled']:
                if scores.get('motion', 0) > config.ANTI_SPOOFING['motion']['threshold']:
                    passed += 1
            if config.ANTI_SPOOFING['glare']['enabled']:
                if scores.get('glare', 0) > config.ANTI_SPOOFING['glare']['threshold']:
                    passed += 1

            min_passed = config.ANTI_SPOOFING.get('min_passed_checks', 2)
            is_real = (confidence >= config.ANTI_SPOOFING['confidence_threshold']) and (passed >= min_passed)
            
            return {
                'is_real': is_real,
                'confidence': confidence,
                'method': config.ANTI_SPOOFING['method'],
                'details': scores,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur dans la détection anti-spoofing: {e}")
            return {
                'is_real': False,  # Sécurité: refuser par défaut en cas d'erreur
                'confidence': 0.0,
                'method': 'error',
                'details': {'error': str(e)},
                'timestamp': datetime.now().isoformat()
            }

    def _detect_texture(self, image: np.ndarray) -> float:
        """
        Analyse la texture du visage (LBP).
        Les vraies faces ont une texture plus naturelle que les photos.
        
        Args:
            image: Image du visage
            
        Returns:
            Score de vivacité (0-1), >0.6 = réel
        """
        try:
            # Convertir en niveaux de gris si nécessaire
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Redimensionner pour la cohérence
            gray = cv2.resize(gray, (100, 100))
            
            # Calculer le LBP (Local Binary Pattern)
            lbp_texture = self._calculate_lbp(gray)
            
            # Analyser la distribution de texture
            # Les photos ont une distribution plus régulière
            hist = cv2.calcHist([lbp_texture], [0], None, [256], [0, 256])
            hist = cv2.normalize(hist, hist).flatten()
            
            # Calculer la variance (plus élevée = plus naturelle)
            variance = np.var(hist)
            
            # Normaliser le score
            # Ajustement du facteur pour que les visages réels obtiennent un score d'environ 0.8+
            score = min(variance / 0.0035, 1.0)  
            
            return score
            
        except Exception as e:
            logger.warning(f"Erreur texture detection: {e}")
            return 0.5

    def _detect_color_spoofing(self, image: np.ndarray) -> float:
        """
        Analyse la distribution des couleurs.
        Les photos ont des canaux de couleur plus corrélés.
        
        Args:
            image: Image BGR
            
        Returns:
            Score de vivacité (0-1), >0.5 = réel
        """
        try:
            # Convertir en HSV
            if len(image.shape) == 2:
                return 0.5  # Image grayscale, pas d'info couleur
            
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            
            # Analyser les canaux
            h_hist = cv2.calcHist([hsv], [0], None, [256], [0, 256])
            s_hist = cv2.calcHist([hsv], [1], None, [256], [0, 256])
            v_hist = cv2.calcHist([hsv], [2], None, [256], [0, 256])
            
            # Normaliser
            h_hist = cv2.normalize(h_hist, h_hist).flatten()
            s_hist = cv2.normalize(s_hist, s_hist).flatten()
            v_hist = cv2.normalize(v_hist, v_hist).flatten()
            
            # Calculer la variance de chaque canal
            h_var = np.var(h_hist)
            s_var = np.var(s_hist)
            v_var = np.var(v_hist)
            
            # Les vraies faces ont une saturation et luminosité variées
            # Ajustement pour donner des scores de ~0.8 à 1.0 aux vrais visages
            score = (h_var * 0.3 + s_var * 0.4 + v_var * 0.3) / 0.0025
            score = min(score, 1.0)
            
            return score
            
        except Exception as e:
            logger.warning(f"Erreur color detection: {e}")
            return 0.5

    def _detect_frequency_spoofing(self, image: np.ndarray) -> float:
        """
        Analyse le domaine fréquentiel (FFT).
        Les photos ont des patterns fréquentiels distincts.
        
        Args:
            image: Image
            
        Returns:
            Score de vivacité (0-1), >0.55 = réel
        """
        try:
            # Convertir en niveaux de gris
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            gray = cv2.resize(gray, (100, 100))
            
            # Appliquer la FFT
            fft = np.fft.fft2(gray)
            fft_shift = np.fft.fftshift(fft)
            magnitude = np.abs(fft_shift)
            magnitude = np.log1p(magnitude)
            
            # Analyser les hautes fréquences
            h, w = magnitude.shape
            center_h, center_w = h // 2, w // 2
            
            # Région central (basses fréquences)
            low_freq = magnitude[center_h-20:center_h+20, center_w-20:center_w+20]
            
            # Région périphérique (hautes fréquences)
            high_freq_regions = [
                magnitude[:20, :],
                magnitude[-20:, :],
                magnitude[:, :20],
                magnitude[:, -20:]
            ]
            
            low_energy = np.sum(low_freq ** 2)
            high_energy = sum(np.sum(region ** 2) for region in high_freq_regions)
            
            # Ratio d'énergie haute fréquence
            if low_energy == 0:
                ratio = 0
            else:
                ratio = high_energy / low_energy
            
            # Les vraies faces ont plus d'énergie haute fréquence (ratio ~2.5)
            # Mais un ratio extrêmement élevé (> 6.0) indique un écran de téléphone (Moiré)
            if ratio > 6.0:
                # Moiré pattern -> baisser drastiquement le score
                score = max(0.0, 1.0 - (ratio - 6.0) * 0.3)
            else:
                score = ratio / 2.5
                score = min(score, 1.0)
            
            return score
            
        except Exception as e:
            logger.warning(f"Erreur frequency detection: {e}")
            return 0.5

    def _detect_screen_glare(self, image: np.ndarray) -> float:
        """
        Détecte des reflets d'écran (forte luminosité et faible saturation).
        Un ratio élevé indique une présentation via écran.
        
        Args:
            image: Image BGR
            
        Returns:
            Score de vivacité (0-1), >0.55 = réel
        """
        try:
            if len(image.shape) == 2:
                return 0.5

            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            v = hsv[..., 2].astype(np.float32) / 255.0
            s = hsv[..., 1].astype(np.float32) / 255.0

            glare_mask = (v >= config.ANTI_SPOOFING['glare']['v_threshold']) & (
                s <= config.ANTI_SPOOFING['glare']['s_threshold']
            )
            glare_ratio = float(np.mean(glare_mask))
            ratio_norm = max(config.ANTI_SPOOFING['glare']['ratio_norm'], 1e-6)

            score = 1.0 - min(glare_ratio / ratio_norm, 1.0)
            return max(0.0, min(1.0, score))

        except Exception as e:
            logger.warning(f"Erreur glare detection: {e}")
            return 0.5

    def _detect_motion(self, gray: np.ndarray) -> Optional[float]:
        """
        Détecte le mouvement optique.
        Les vraies faces montrent du mouvement naturel dans une séquence.
        
        Args:
            gray: Image en niveaux de gris
            
        Returns:
            Score de vivacité (0-1), >0.4 = réel
        """
        try:
            gray = cv2.resize(gray, (100, 100))
            
            if self.last_gray is None:
                self.last_gray = gray
                self.motion_buffer.clear()
                return None
            
            # Calculer le flux optique
            flow = cv2.calcOpticalFlowFarneback(
                self.last_gray, gray, None,
                pyr_scale=0.5, levels=3, winsize=15,
                iterations=3, poly_n=5, poly_sigma=1.2, flags=0
            )
            
            # Calculer la magnitude du mouvement
            magnitude = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)
            mean_motion = np.mean(magnitude)
            
            # Ajouter au buffer
            self.motion_buffer.append(mean_motion)
            if len(self.motion_buffer) > self.max_buffer_size:
                self.motion_buffer.pop(0)
            
            self.last_gray = gray.copy()
            
            # Analyser la variance du mouvement
            if len(self.motion_buffer) >= config.ANTI_SPOOFING['motion']['required_frames']:
                motion_variance = np.var(self.motion_buffer)
                # Les vraies faces ont une variance de mouvement modérée 
                # Ajustement du facteur pour obtenir un score cohérent > 0.4
                score = min(motion_variance / 1.0, 1.0)
            else:
                score = None
            
            return score
            
        except Exception as e:
            logger.warning(f"Erreur motion detection: {e}")
            return 0.5

    def _calculate_lbp(self, image: np.ndarray) -> np.ndarray:
        """
        Calcule l'opérateur LBP.
        
        Args:
            image: Image en niveaux de gris
            
        Returns:
            Image LBP
        """
        h, w = image.shape
        lbp = np.zeros_like(image, dtype=np.uint8)
        
        for i in range(1, h - 1):
            for j in range(1, w - 1):
                center = image[i, j]
                
                # 8 voisins
                neighbors = [
                    image[i-1, j-1], image[i-1, j], image[i-1, j+1],
                    image[i, j+1], image[i+1, j+1], image[i+1, j],
                    image[i+1, j-1], image[i, j-1]
                ]
                
                # Calculer le code LBP
                code = 0
                for k, neighbor in enumerate(neighbors):
                    if neighbor >= center:
                        code |= (1 << k)
                
                lbp[i, j] = code
        
        return lbp

    def _combine_scores(self, scores: Dict[str, float]) -> float:
        """
        Combine les scores de différentes méthodes.
        
        Args:
            scores: Dict avec les scores par méthode
            
        Returns:
            Score combiné (0-1)
        """
        if not scores:
            return 0.95  # Default: accept (real face likely)
        
        weighted_sum = 0
        total_weight = 0
        
        if 'texture' in scores and isinstance(scores['texture'], (int, float)):
            weight = config.ANTI_SPOOFING['texture']['weight']
            score = scores['texture'] * (scores['texture'] > config.ANTI_SPOOFING['texture']['threshold'])
            weighted_sum += score * weight
            total_weight += weight
        
        if 'color' in scores and isinstance(scores['color'], (int, float)):
            weight = config.ANTI_SPOOFING['color']['weight']
            score = scores['color'] * (scores['color'] > config.ANTI_SPOOFING['color']['threshold'])
            weighted_sum += score * weight
            total_weight += weight
        
        if 'frequency' in scores and isinstance(scores['frequency'], (int, float)):
            weight = config.ANTI_SPOOFING['frequency']['weight']
            score = scores['frequency'] * (scores['frequency'] > config.ANTI_SPOOFING['frequency']['threshold'])
            weighted_sum += score * weight
            total_weight += weight
        
        if 'motion' in scores and isinstance(scores['motion'], (int, float)):
            weight = config.ANTI_SPOOFING['motion']['weight']
            score = scores['motion'] * (scores['motion'] > config.ANTI_SPOOFING['motion']['threshold'])
            weighted_sum += score * weight
            total_weight += weight

        if 'glare' in scores and isinstance(scores['glare'], (int, float)):
            weight = config.ANTI_SPOOFING['glare']['weight']
            score = scores['glare'] * (scores['glare'] > config.ANTI_SPOOFING['glare']['threshold'])
            weighted_sum += score * weight
            total_weight += weight
        
        # Screen patterns detection - only low weight, auxiliary check
        if 'screen_patterns' in scores and isinstance(scores['screen_patterns'], (int, float)):
            screen_pattern_weight = 0.10  # Very low weight - auxiliary only
            score = scores['screen_patterns'] * (scores['screen_patterns'] > 0.5)
            weighted_sum += score * screen_pattern_weight
            total_weight += screen_pattern_weight
        
        if total_weight == 0:
            return 0.95  # Default: accept (real face likely)
        
        final_score = weighted_sum / total_weight if total_weight > 0 else 0.95
        return max(0.55, min(1.0, final_score))  # Range [0.55 - 1.0] to favor real faces

    def _detect_screen_patterns(self, image: np.ndarray) -> float:
        """
        Détecte les patterns spécifiques aux écrans (téléphones, tablettes, écrans).
        Les écrans produisent des Moiré patterns et des reflets caractéristiques.
        
        Args:
            image: Image BGR
            
        Returns:
            Score de vivacité (0-1), >0.6 = réel
        """
        try:
            if len(image.shape) == 2:
                gray = image
            else:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # Redimensionner pour la cohérence
            gray = cv2.resize(gray, (100, 100))
            
            # 1. Détecter les patterns répétitifs (Moiré)
            # FFT pour détecter les fréquences régulières des écrans
            fft = np.fft.fft2(gray)
            fft_shift = np.fft.fftshift(fft)
            magnitude = np.abs(fft_shift)
            
            # Normaliser la magnitude
            magnitude = np.log1p(magnitude) / (np.log1p(np.max(magnitude)) + 1e-6)
            
            # Chercher des pics d'énergie réguliers (Moiré)
            h, w = magnitude.shape
            center_h, center_w = h // 2, w // 2
            
            # Vérifier les patterns aux basses fréquences (marques d'écran)
            low_freq_region = magnitude[center_h-15:center_h+15, center_w-15:center_w+15]
            periodicity_score = np.std(low_freq_region)
            
            # 2. Détecter les reflets typiques d'écran (zones très brillantes et saturées)
            if len(image.shape) == 3:
                hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
                v = hsv[..., 2].astype(np.float32) / 255.0
                s = hsv[..., 1].astype(np.float32) / 255.0
                
                # Écrans typiquement: haute luminosité + basse saturation
                # Mais ajuster les seuils pour ne pas détecter les vraies faces
                bright_low_sat = np.sum((v >= 0.80) & (s <= 0.20))  # Plus stricts
                total_pixels = hsv.shape[0] * hsv.shape[1]
                bright_ratio = bright_low_sat / total_pixels
                
                # 3. Analyser la distribution des bords (écrans ont moins de texture)
                edges = cv2.Canny(gray, 50, 150)
                edge_ratio = np.sum(edges > 0) / edges.size
            else:
                bright_ratio = 0
                edges = cv2.Canny(gray, 50, 150)
                edge_ratio = np.sum(edges > 0) / edges.size
            
            # Combiner les indicateurs d'écran
            # Peu d'arêtes + haute luminosité/basse saturation + patterns réguliers = écran probable
            screen_score = 0
            
            # Weights réduites - seulement si tous les indicateurs pointent vers un écran
            if periodicity_score > 0.20:  # Patterns réguliers TRÈS marqués
                screen_score += 0.2
            if bright_ratio > 0.20:  # Zones très brillantes et peu saturées - très marqué
                screen_score += 0.3
            if edge_ratio < 0.04:  # Très peu de texture
                screen_score += 0.2
            
            # Inverser le score: plus le score d'écran est élevé, moins c'est réel
            # Les vraies faces doivent obtenir un score > 0.6 (screen_score < 0.4)
            liveness_score = 1.0 - min(screen_score, 1.0)
            
            return liveness_score
            
        except Exception as e:
            logger.warning(f"Erreur screen pattern detection: {e}")
            return 0.7  # Par défaut accepter (vraie face probable)

    def reset(self):
        """Réinitialise l'état du détecteur."""
        self.motion_buffer.clear()
        self.last_gray = None


# Instance globale
anti_spoofing_detector = AntiSpoofingDetector()
