# -*- coding: utf-8 -*-
"""
Module de Tatouage Numérique (Digital Watermarking)
===================================================
Implémentation des méthodes LSB et DCT pour le tatouage des logs d'accès.
Permet de garantir l'intégrité et la traçabilité des journaux.
"""

import cv2
import numpy as np
import hashlib
import json
import os
from datetime import datetime
from typing import Tuple, Optional, Dict, Any
from PIL import Image
import io

import config


class WatermarkManager:
    """
    Gestionnaire de tatouage numérique utilisant les méthodes LSB et DCT.
    
    - LSB (Least Significant Bit): Modification des bits de poids faible
    - DCT (Discrete Cosine Transform): Modification dans le domaine fréquentiel
    """

    def __init__(self, method: str = None, secret_key: str = None):
        """
        Initialise le gestionnaire de tatouage.
        
        Args:
            method: Méthode de tatouage ('LSB' ou 'DCT')
            secret_key: Clé secrète pour le chiffrement du tatouage
        """
        self.method = method or config.WATERMARK['method']
        self.secret_key = secret_key or config.WATERMARK['secret_key']
        self.lsb_bits = config.WATERMARK['lsb_bits']
        self.dct_strength = config.WATERMARK['dct_strength']
        self.block_size = config.WATERMARK['block_size']

    def _string_to_binary(self, text: str) -> str:
        """Convertit une chaîne de caractères en binaire."""
        binary = ''.join(format(ord(char), '08b') for char in text)
        return binary

    def _binary_to_string(self, binary: str) -> str:
        """Convertit du binaire en chaîne de caractères."""
        chars = [binary[i:i+8] for i in range(0, len(binary), 8)]
        text = ''.join(chr(int(char, 2)) for char in chars if len(char) == 8)
        return text

    def _compute_hash(self, data: str) -> str:
        """Calcule le hash SHA-256 des données."""
        if not self.secret_key:
            raise ValueError("Set BIO_WATERMARK_SECRET_KEY before creating or verifying watermarks.")
        combined = f"{data}{self.secret_key}"
        return hashlib.sha256(combined.encode()).hexdigest()

    def _prepare_watermark_data(self, log_data: Dict) -> str:
        """
        Prépare les données du log pour le tatouage.
        
        Args:
            log_data: Dictionnaire contenant les données du log
            
        Returns:
            Chaîne formatée pour le tatouage
        """
        # Créer une représentation compacte du log
        essential_data = {
            'id': log_data.get('id'),
            'ts': log_data.get('timestamp'),
            'at': log_data.get('access_type'),
            'ar': log_data.get('access_result'),
            'uid': log_data.get('user_id'),
        }
        
        # Ajouter le hash pour l'intégrité
        data_str = json.dumps(essential_data, sort_keys=True)
        data_hash = self._compute_hash(data_str)[:16]  # 16 premiers caractères du hash
        
        # Format: [MARKER][LENGTH][DATA][HASH][END_MARKER]
        watermark_content = f"<<BIO>>{data_str}|{data_hash}<<END>>"
        
        return watermark_content

    # =========================================================================
    # MÉTHODE LSB (Least Significant Bit)
    # =========================================================================

    def embed_lsb(self, image: np.ndarray, data: str) -> Tuple[np.ndarray, str]:
        """
        Embarque des données dans une image en utilisant la méthode LSB.
        
        Args:
            image: Image source (BGR ou RGB)
            data: Données à embarquer
            
        Returns:
            Tuple (image tatouée, hash de vérification)
        """
        # Copier l'image
        watermarked = image.copy()
        
        # Préparer les données binaires avec marqueur de fin
        binary_data = self._string_to_binary(data) + '1111111111111110'  # Delimiter
        data_index = 0
        data_len = len(binary_data)
        
        # Vérifier la capacité
        max_capacity = image.shape[0] * image.shape[1] * 3 * self.lsb_bits
        if data_len > max_capacity:
            raise ValueError(f"Données trop volumineuses: {data_len} bits > {max_capacity} bits")
        
        # Embarquer les données
        for row in range(watermarked.shape[0]):
            for col in range(watermarked.shape[1]):
                for channel in range(3):  # BGR
                    if data_index < data_len:
                        # Modifier les n bits de poids faible
                        pixel_value = watermarked[row, col, channel]
                        
                        # Effacer les n bits de poids faible
                        pixel_value = (pixel_value >> self.lsb_bits) << self.lsb_bits
                        
                        # Extraire les bits à insérer
                        bits_to_insert = binary_data[data_index:data_index + self.lsb_bits]
                        if len(bits_to_insert) < self.lsb_bits:
                            bits_to_insert = bits_to_insert.ljust(self.lsb_bits, '0')
                        
                        # Insérer les bits
                        insert_value = int(bits_to_insert, 2)
                        watermarked[row, col, channel] = np.uint8(pixel_value | insert_value)
                        
                        data_index += self.lsb_bits
                    else:
                        break
        
        # Calculer le hash de vérification
        verification_hash = self._compute_hash(data)
        
        return watermarked, verification_hash

    def extract_lsb(self, image: np.ndarray) -> Tuple[Optional[str], bool]:
        """
        Extrait les données tatouées d'une image en utilisant la méthode LSB.
        
        Args:
            image: Image tatouée
            
        Returns:
            Tuple (données extraites ou None, intégrité vérifiée)
        """
        binary_data = ''
        delimiter = '1111111111111110'
        
        # Extraire les bits
        for row in range(image.shape[0]):
            for col in range(image.shape[1]):
                for channel in range(3):
                    pixel_value = image[row, col, channel]
                    # Extraire les n bits de poids faible
                    extracted_bits = format(pixel_value & ((1 << self.lsb_bits) - 1), 
                                           f'0{self.lsb_bits}b')
                    binary_data += extracted_bits
                    
                    # Vérifier le délimiteur
                    if len(binary_data) >= 16 and binary_data[-16:] == delimiter:
                        # Extraire les données sans le délimiteur
                        data_binary = binary_data[:-16]
                        extracted_data = self._binary_to_string(data_binary)
                        
                        # Vérifier l'intégrité
                        if '<<BIO>>' in extracted_data and '<<END>>' in extracted_data:
                            try:
                                start = extracted_data.find('<<BIO>>') + 7
                                end = extracted_data.find('<<END>>')
                                content = extracted_data[start:end]
                                
                                # Séparer les données et le hash
                                parts = content.rsplit('|', 1)
                                if len(parts) == 2:
                                    data_str, stored_hash = parts
                                    computed_hash = self._compute_hash(data_str)[:16]
                                    is_valid = (stored_hash == computed_hash)
                                    return data_str, is_valid
                            except Exception:
                                pass
                        
                        return extracted_data, False
        
        return None, False

    # =========================================================================
    # MÉTHODE DCT (Discrete Cosine Transform)
    # =========================================================================

    def embed_dct(self, image: np.ndarray, data: str) -> Tuple[np.ndarray, str]:
        """
        Embarque des données dans une image en utilisant la méthode DCT.
        Plus robuste à la compression JPEG.
        
        Args:
            image: Image source (BGR)
            data: Données à embarquer
            
        Returns:
            Tuple (image tatouée, hash de vérification)
        """
        # Convertir en YCrCb (travailler sur la luminance)
        if len(image.shape) == 3:
            ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
            y_channel = ycrcb[:, :, 0].astype(np.float64)
        else:
            y_channel = image.astype(np.float64)
        
        # Préparer les données binaires
        binary_data = self._string_to_binary(data)
        data_len = len(binary_data)
        
        # Calculer le nombre de blocs disponibles
        h, w = y_channel.shape
        blocks_h = h // self.block_size
        blocks_w = w // self.block_size
        total_blocks = blocks_h * blocks_w
        
        if data_len > total_blocks:
            raise ValueError(f"Données trop volumineuses: {data_len} bits > {total_blocks} blocs")
        
        # Embarquer les données dans les coefficients DCT
        data_index = 0
        watermarked_y = y_channel.copy()
        
        # Ajouter la longueur des données au début (16 bits)
        length_binary = format(data_len, '016b')
        full_data = length_binary + binary_data
        
        for i in range(blocks_h):
            for j in range(blocks_w):
                if data_index < len(full_data):
                    # Extraire le bloc
                    block = watermarked_y[
                        i * self.block_size:(i + 1) * self.block_size,
                        j * self.block_size:(j + 1) * self.block_size
                    ]
                    
                    # Appliquer DCT
                    dct_block = cv2.dct(block)
                    
                    # Modifier le coefficient en position (4, 4) - fréquence moyenne
                    bit = int(full_data[data_index])
                    
                    # Quantification selon le bit
                    coef = dct_block[4, 4]
                    quantized = round(coef / self.dct_strength) * self.dct_strength
                    
                    if bit == 1:
                        dct_block[4, 4] = quantized + self.dct_strength / 2
                    else:
                        dct_block[4, 4] = quantized
                    
                    # Appliquer IDCT
                    idct_block = cv2.idct(dct_block)
                    watermarked_y[
                        i * self.block_size:(i + 1) * self.block_size,
                        j * self.block_size:(j + 1) * self.block_size
                    ] = idct_block
                    
                    data_index += 1
        
        # Reconstruire l'image couleur
        watermarked_y = np.clip(watermarked_y, 0, 255).astype(np.uint8)
        
        if len(image.shape) == 3:
            ycrcb[:, :, 0] = watermarked_y
            watermarked = cv2.cvtColor(ycrcb, cv2.COLOR_YCrCb2BGR)
        else:
            watermarked = watermarked_y
        
        # Hash de vérification
        verification_hash = self._compute_hash(data)
        
        return watermarked, verification_hash

    def extract_dct(self, image: np.ndarray) -> Tuple[Optional[str], bool]:
        """
        Extrait les données tatouées d'une image en utilisant la méthode DCT.
        
        Args:
            image: Image tatouée
            
        Returns:
            Tuple (données extraites ou None, intégrité vérifiée)
        """
        # Convertir en YCrCb
        if len(image.shape) == 3:
            ycrcb = cv2.cvtColor(image, cv2.COLOR_BGR2YCrCb)
            y_channel = ycrcb[:, :, 0].astype(np.float64)
        else:
            y_channel = image.astype(np.float64)
        
        h, w = y_channel.shape
        blocks_h = h // self.block_size
        blocks_w = w // self.block_size
        
        # Extraire d'abord la longueur (16 premiers bits)
        extracted_bits = ''
        
        for i in range(blocks_h):
            for j in range(blocks_w):
                block = y_channel[
                    i * self.block_size:(i + 1) * self.block_size,
                    j * self.block_size:(j + 1) * self.block_size
                ]
                
                dct_block = cv2.dct(block)
                coef = dct_block[4, 4]
                
                # Déterminer le bit
                quantized = round(coef / self.dct_strength) * self.dct_strength
                diff = coef - quantized
                
                if diff > self.dct_strength / 4:
                    extracted_bits += '1'
                else:
                    extracted_bits += '0'
                
                # Vérifier si on a assez de bits pour la longueur
                if len(extracted_bits) == 16:
                    try:
                        data_length = int(extracted_bits, 2)
                        if data_length <= 0 or data_length > (blocks_h * blocks_w - 16):
                            return None, False
                    except ValueError:
                        return None, False
                
                # Vérifier si on a extrait toutes les données
                if len(extracted_bits) > 16:
                    try:
                        data_length = int(extracted_bits[:16], 2)
                        if len(extracted_bits) == 16 + data_length:
                            data_binary = extracted_bits[16:]
                            extracted_data = self._binary_to_string(data_binary)
                            
                            # Vérifier l'intégrité
                            if '<<BIO>>' in extracted_data and '<<END>>' in extracted_data:
                                try:
                                    start = extracted_data.find('<<BIO>>') + 7
                                    end = extracted_data.find('<<END>>')
                                    content = extracted_data[start:end]
                                    
                                    parts = content.rsplit('|', 1)
                                    if len(parts) == 2:
                                        data_str, stored_hash = parts
                                        computed_hash = self._compute_hash(data_str)[:16]
                                        is_valid = (stored_hash == computed_hash)
                                        return data_str, is_valid
                                except Exception:
                                    pass
                            
                            return extracted_data, False
                    except Exception:
                        pass
        
        return None, False

    # =========================================================================
    # INTERFACE UNIFIÉE
    # =========================================================================

    def embed_watermark(self, image: np.ndarray, log_data: Dict) -> Tuple[np.ndarray, str]:
        """
        Embarque un tatouage dans une image selon la méthode configurée.
        
        Args:
            image: Image source
            log_data: Données du log à embarquer
            
        Returns:
            Tuple (image tatouée, hash de vérification)
        """
        watermark_data = self._prepare_watermark_data(log_data)
        
        if self.method == 'DCT':
            return self.embed_dct(image, watermark_data)
        else:  # LSB par défaut
            return self.embed_lsb(image, watermark_data)

    def extract_watermark(self, image: np.ndarray) -> Tuple[Optional[Dict], bool, str]:
        """
        Extrait et vérifie un tatouage d'une image.
        
        Args:
            image: Image tatouée
            
        Returns:
            Tuple (données extraites, intégrité vérifiée, message de statut)
        """
        # Essayer la méthode configurée en premier
        if self.method == 'DCT':
            data, is_valid = self.extract_dct(image)
            if data is None:
                # Essayer LSB en fallback
                data, is_valid = self.extract_lsb(image)
        else:
            data, is_valid = self.extract_lsb(image)
            if data is None:
                # Essayer DCT en fallback
                data, is_valid = self.extract_dct(image)
        
        if data is None:
            return None, False, "Aucun tatouage détecté"
        
        # Parser les données JSON
        try:
            log_data = json.loads(data)
            if is_valid:
                return log_data, True, "Tatouage valide - Intégrité vérifiée"
            else:
                return log_data, False, "Tatouage extrait mais intégrité compromise"
        except json.JSONDecodeError:
            return None, False, "Données corrompues ou format invalide"

    def watermark_log_image(self, log_data: Dict, capture_path: str = None) -> Tuple[str, str]:
        """
        Crée une image tatouée représentant un log d'accès.
        
        Args:
            log_data: Données du log
            capture_path: Chemin vers une image de capture (optionnel)
            
        Returns:
            Tuple (chemin de l'image tatouée, hash de vérification)
        """
        # Charger ou créer l'image de base
        if capture_path and os.path.exists(capture_path):
            image = cv2.imread(capture_path)
        else:
            # Créer une image de log textuelle
            image = self._create_log_image(log_data)
        
        # Appliquer le tatouage
        watermarked, verification_hash = self.embed_watermark(image, log_data)
        
        # Sauvegarder l'image tatouée
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"log_watermarked_{log_data.get('id', 'unknown')}_{timestamp}.png"
        filepath = os.path.join(config.WATERMARKED_LOGS_DIR, filename)
        
        cv2.imwrite(filepath, watermarked)
        
        return filepath, verification_hash

    def _create_log_image(self, log_data: Dict, size: Tuple[int, int] = (800, 600)) -> np.ndarray:
        """
        Crée une image représentant visuellement un log d'accès.
        
        Args:
            log_data: Données du log
            size: Taille de l'image (largeur, hauteur)
            
        Returns:
            Image numpy
        """
        # Créer une image blanche
        image = np.ones((size[1], size[0], 3), dtype=np.uint8) * 255
        
        # Ajouter un en-tête
        cv2.rectangle(image, (0, 0), (size[0], 80), (50, 50, 150), -1)
        cv2.putText(image, "JOURNAL D'ACCES BIOMETRIQUE",
                   (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
        
        # Informations du log
        y_pos = 120
        line_height = 40
        
        info_lines = [
            f"ID Log: {log_data.get('id', 'N/A')}",
            f"Date/Heure: {log_data.get('timestamp', 'N/A')}",
            f"Type d'acces: {log_data.get('access_type', 'N/A')}",
            f"Resultat: {log_data.get('access_result', 'N/A')}",
            f"Utilisateur ID: {log_data.get('user_id', 'N/A')}",
            f"Zone: {log_data.get('zone_name', 'N/A')}",
            f"Confiance: {log_data.get('confidence_score', 'N/A')}%",
        ]
        
        for line in info_lines:
            cv2.putText(image, line, (30, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
            y_pos += line_height
        
        # Ajouter un indicateur de tatouage
        cv2.rectangle(image, (0, size[1] - 60), (size[0], size[1]), (50, 150, 50), -1)
        cv2.putText(image, "DOCUMENT TATOUAGE - INTEGRITE VERIFIABLE",
                   (20, size[1] - 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        return image

    def verify_log_integrity(self, image_path: str) -> Dict[str, Any]:
        """
        Vérifie l'intégrité d'un log tatoué.
        
        Args:
            image_path: Chemin vers l'image tatouée
            
        Returns:
            Dictionnaire avec les résultats de vérification
        """
        result = {
            'is_valid': False,
            'watermark_found': False,
            'data': None,
            'message': '',
            'verification_time': datetime.now().isoformat()
        }
        
        if not os.path.exists(image_path):
            result['message'] = "Fichier non trouvé"
            return result
        
        # Charger l'image
        image = cv2.imread(image_path)
        if image is None:
            result['message'] = "Impossible de charger l'image"
            return result
        
        # Extraire et vérifier le tatouage
        data, is_valid, message = self.extract_watermark(image)
        
        result['watermark_found'] = data is not None
        result['is_valid'] = is_valid
        result['data'] = data
        result['message'] = message
        
        return result

    def test_robustness(self, image_path: str) -> Dict[str, bool]:
        """
        Teste la robustesse du tatouage face à différentes attaques.
        
        Args:
            image_path: Chemin vers l'image tatouée originale
            
        Returns:
            Dictionnaire des résultats de test
        """
        results = {
            'original': False,
            'jpeg_compression_90': False,
            'jpeg_compression_70': False,
            'jpeg_compression_50': False,
            'resize_50': False,
            'resize_75': False,
            'gaussian_noise': False,
            'brightness_change': False,
        }
        
        # Charger l'image originale
        original = cv2.imread(image_path)
        if original is None:
            return results
        
        # Test original
        data, is_valid, _ = self.extract_watermark(original)
        results['original'] = is_valid
        
        # Test compression JPEG
        for quality, key in [(90, 'jpeg_compression_90'), 
                             (70, 'jpeg_compression_70'),
                             (50, 'jpeg_compression_50')]:
            encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), quality]
            _, encoded = cv2.imencode('.jpg', original, encode_param)
            compressed = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
            data, is_valid, _ = self.extract_watermark(compressed)
            results[key] = is_valid
        
        # Test redimensionnement
        for scale, key in [(0.5, 'resize_50'), (0.75, 'resize_75')]:
            h, w = original.shape[:2]
            resized = cv2.resize(original, (int(w * scale), int(h * scale)))
            resized = cv2.resize(resized, (w, h))  # Retour à la taille originale
            data, is_valid, _ = self.extract_watermark(resized)
            results[key] = is_valid
        
        # Test bruit gaussien
        noise = np.random.normal(0, 10, original.shape).astype(np.uint8)
        noisy = cv2.add(original, noise)
        data, is_valid, _ = self.extract_watermark(noisy)
        results['gaussian_noise'] = is_valid
        
        # Test changement de luminosité
        bright = cv2.convertScaleAbs(original, alpha=1.2, beta=20)
        data, is_valid, _ = self.extract_watermark(bright)
        results['brightness_change'] = is_valid
        
        return results


# Instance globale
watermark_manager = WatermarkManager()
