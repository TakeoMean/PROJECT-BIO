# -*- coding: utf-8 -*-
"""
Module de Base de Données SQLite
================================
Gestion de la persistance des données utilisateurs, autorisations et logs d'accès.
Conforme aux exigences RGPD pour les données biométriques.
"""

import sqlite3
import hashlib
import json
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager

import config


class DatabaseManager:
    """
    Gestionnaire de base de données SQLite pour le système de contrôle d'accès.
    Gère les utilisateurs, les autorisations, les logs d'accès et les alertes.
    """

    def __init__(self, db_path: str = None):
        """
        Initialise le gestionnaire de base de données.
        
        Args:
            db_path: Chemin vers le fichier de base de données SQLite
        """
        self.db_path = db_path or config.DATABASE_PATH
        self._ensure_directory()
        self._init_database()

    def _ensure_directory(self):
        """Crée le répertoire de la base de données s'il n'existe pas."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    @contextmanager
    def _get_connection(self):
        """
        Gestionnaire de contexte pour les connexions à la base de données.
        Assure la fermeture correcte des connexions.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _init_database(self):
        """Initialise les tables de la base de données."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Table des utilisateurs
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    full_name TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
                    department TEXT,
                    role TEXT DEFAULT 'user',
                    face_encoding BLOB,
                    is_active INTEGER DEFAULT 1,
                    is_authorized INTEGER DEFAULT 0,
                    consent_given INTEGER DEFAULT 0,
                    consent_date TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_access TEXT,
                    failed_attempts INTEGER DEFAULT 0,
                    locked_until TEXT
                )
            ''')

            # Table des zones d'accès
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS access_zones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    security_level INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Table des autorisations (relation utilisateur-zone)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS authorizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    zone_id INTEGER NOT NULL,
                    granted_by INTEGER,
                    valid_from TEXT,
                    valid_until TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (zone_id) REFERENCES access_zones(id),
                    FOREIGN KEY (granted_by) REFERENCES users(id),
                    UNIQUE(user_id, zone_id)
                )
            ''')

            # Table des logs d'accès
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS access_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    zone_id INTEGER,
                    access_type TEXT NOT NULL,
                    access_result TEXT NOT NULL,
                    confidence_score REAL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    ip_address TEXT,
                    device_info TEXT,
                    capture_path TEXT,
                    watermark_hash TEXT,
                    is_watermarked INTEGER DEFAULT 0,
                    watermarked_image_path TEXT,
                    details TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (zone_id) REFERENCES access_zones(id)
                )
            ''')

            # Table des alertes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    log_id INTEGER,
                    alert_level INTEGER NOT NULL,
                    alert_type TEXT NOT NULL,
                    message TEXT,
                    is_acknowledged INTEGER DEFAULT 0,
                    acknowledged_by INTEGER,
                    acknowledged_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (log_id) REFERENCES access_logs(id),
                    FOREIGN KEY (acknowledged_by) REFERENCES users(id)
                )
            ''')

            # Table des sessions administrateur
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    session_token TEXT UNIQUE NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    expires_at TEXT NOT NULL,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

            # Table de configuration système
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Créer zone par défaut si elle n'existe pas
            cursor.execute('''
                INSERT OR IGNORE INTO access_zones (name, description, security_level)
                VALUES ('Zone Principale', 'Zone d''accès principale', 1)
            ''')

    # =========================================================================
    # GESTION DES UTILISATEURS
    # =========================================================================

    def add_user(self, username: str, full_name: str, email: str = None,
                 phone: str = None, department: str = None, role: str = 'user',
                 is_authorized: bool = False, consent_given: bool = False) -> int:
        """
        Ajoute un nouvel utilisateur dans la base de données.
        
        Args:
            username: Identifiant unique de l'utilisateur
            full_name: Nom complet
            email: Adresse email
            phone: Numéro de téléphone
            department: Département
            role: Rôle (user, admin, security)
            is_authorized: Si l'utilisateur est autorisé à accéder
            consent_given: Consentement RGPD donné
            
        Returns:
            ID de l'utilisateur créé
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            consent_date = datetime.now().isoformat() if consent_given else None
            cursor.execute('''
                INSERT INTO users (username, full_name, email, phone, department, 
                                   role, is_authorized, consent_given, consent_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (username, full_name, email, phone, department, role, 
                  int(is_authorized), int(consent_given), consent_date))
            return cursor.lastrowid

    def update_user(self, user_id: int, **kwargs) -> bool:
        """
        Met à jour les informations d'un utilisateur.
        
        Args:
            user_id: ID de l'utilisateur
            **kwargs: Champs à mettre à jour
            
        Returns:
            True si la mise à jour a réussi
        """
        allowed_fields = {'full_name', 'email', 'phone', 'department', 'role',
                          'is_active', 'is_authorized', 'consent_given', 'face_encoding'}
        
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False

        updates['updated_at'] = datetime.now().isoformat()
        
        set_clause = ', '.join(f'{k} = ?' for k in updates.keys())
        values = list(updates.values()) + [user_id]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE users SET {set_clause} WHERE id = ?
            ''', values)
            return cursor.rowcount > 0

    def get_user(self, user_id: int = None, username: str = None) -> Optional[Dict]:
        """
        Récupère un utilisateur par ID ou username.
        
        Args:
            user_id: ID de l'utilisateur
            username: Nom d'utilisateur
            
        Returns:
            Dictionnaire contenant les informations de l'utilisateur
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            elif username:
                cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            else:
                return None
            
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_all_users(self, active_only: bool = True) -> List[Dict]:
        """
        Récupère tous les utilisateurs.
        
        Args:
            active_only: Ne retourner que les utilisateurs actifs
            
        Returns:
            Liste des utilisateurs
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if active_only:
                cursor.execute('SELECT * FROM users WHERE is_active = 1 ORDER BY full_name')
            else:
                cursor.execute('SELECT * FROM users ORDER BY full_name')
            return [dict(row) for row in cursor.fetchall()]

    def get_authorized_users(self) -> List[Dict]:
        """Récupère tous les utilisateurs autorisés avec leur encodage facial."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM users 
                WHERE is_active = 1 AND is_authorized = 1 AND face_encoding IS NOT NULL
                ORDER BY full_name
            ''')
            return [dict(row) for row in cursor.fetchall()]

    def update_face_encoding(self, user_id: int, face_encoding: bytes) -> bool:
        """
        Met à jour l'encodage facial d'un utilisateur.
        
        Args:
            user_id: ID de l'utilisateur
            face_encoding: Encodage facial en bytes
            
        Returns:
            True si la mise à jour a réussi
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET face_encoding = ?, updated_at = ? WHERE id = ?
            ''', (face_encoding, datetime.now().isoformat(), user_id))
            return cursor.rowcount > 0

    def delete_user(self, user_id: int, hard_delete: bool = False) -> bool:
        """
        Supprime ou désactive un utilisateur (conformité RGPD).
        
        Args:
            user_id: ID de l'utilisateur
            hard_delete: Suppression définitive si True, sinon désactivation
            
        Returns:
            True si l'opération a réussi
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if hard_delete:
                # Anonymiser les logs avant suppression
                cursor.execute('''
                    UPDATE access_logs SET user_id = NULL, details = 'Utilisateur supprimé (RGPD)'
                    WHERE user_id = ?
                ''', (user_id,))
                cursor.execute('DELETE FROM authorizations WHERE user_id = ?', (user_id,))
                cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            else:
                cursor.execute('''
                    UPDATE users SET is_active = 0, face_encoding = NULL, 
                                     updated_at = ? WHERE id = ?
                ''', (datetime.now().isoformat(), user_id))
            return cursor.rowcount > 0

    # =========================================================================
    # GESTION DES ZONES D'ACCÈS
    # =========================================================================

    def add_zone(self, name: str, description: str = None, security_level: int = 1) -> int:
        """Ajoute une nouvelle zone d'accès."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO access_zones (name, description, security_level)
                VALUES (?, ?, ?)
            ''', (name, description, security_level))
            return cursor.lastrowid

    def get_zones(self, active_only: bool = True) -> List[Dict]:
        """Récupère toutes les zones d'accès."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if active_only:
                cursor.execute('SELECT * FROM access_zones WHERE is_active = 1')
            else:
                cursor.execute('SELECT * FROM access_zones')
            return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # GESTION DES AUTORISATIONS
    # =========================================================================

    def grant_authorization(self, user_id: int, zone_id: int, granted_by: int = None,
                           valid_from: str = None, valid_until: str = None) -> int:
        """Accorde une autorisation d'accès à un utilisateur pour une zone."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO authorizations 
                (user_id, zone_id, granted_by, valid_from, valid_until, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
            ''', (user_id, zone_id, granted_by, valid_from, valid_until))
            return cursor.lastrowid

    def revoke_authorization(self, user_id: int, zone_id: int) -> bool:
        """Révoque une autorisation d'accès."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE authorizations SET is_active = 0 
                WHERE user_id = ? AND zone_id = ?
            ''', (user_id, zone_id))
            return cursor.rowcount > 0

    def check_authorization(self, user_id: int, zone_id: int = None) -> bool:
        """Vérifie si un utilisateur est autorisé à accéder à une zone."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            if zone_id:
                cursor.execute('''
                    SELECT * FROM authorizations 
                    WHERE user_id = ? AND zone_id = ? AND is_active = 1
                    AND (valid_from IS NULL OR valid_from <= ?)
                    AND (valid_until IS NULL OR valid_until >= ?)
                ''', (user_id, zone_id, now, now))
            else:
                cursor.execute('''
                    SELECT * FROM authorizations 
                    WHERE user_id = ? AND is_active = 1
                    AND (valid_from IS NULL OR valid_from <= ?)
                    AND (valid_until IS NULL OR valid_until >= ?)
                ''', (user_id, now, now))
            
            return cursor.fetchone() is not None

    # =========================================================================
    # GESTION DES LOGS D'ACCÈS
    # =========================================================================

    def add_access_log(self, access_type: str, access_result: str,
                       user_id: int = None, zone_id: int = None,
                       confidence_score: float = None, capture_path: str = None,
                       details: str = None) -> int:
        """
        Enregistre un événement d'accès dans les logs.
        
        Args:
            access_type: Type d'accès (AUTHORIZED, KNOWN_UNAUTHORIZED, IMPOSTOR, UNKNOWN)
            access_result: Résultat (GRANTED, DENIED, ALARM)
            user_id: ID de l'utilisateur (si identifié)
            zone_id: ID de la zone
            confidence_score: Score de confiance de la reconnaissance
            capture_path: Chemin vers la capture d'écran
            details: Détails supplémentaires
            
        Returns:
            ID du log créé
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO access_logs 
                (user_id, zone_id, access_type, access_result, confidence_score, 
                 capture_path, details, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, zone_id, access_type, access_result, confidence_score,
                  capture_path, details, datetime.now().isoformat()))
            
            log_id = cursor.lastrowid
            
            # Mettre à jour la dernière date d'accès de l'utilisateur
            if user_id:
                cursor.execute('''
                    UPDATE users SET last_access = ? WHERE id = ?
                ''', (datetime.now().isoformat(), user_id))
            
            return log_id

    def update_log_watermark(self, log_id: int, watermark_hash: str,
                             watermarked_image_path: str) -> bool:
        """Met à jour les informations de tatouage d'un log."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE access_logs 
                SET watermark_hash = ?, watermarked_image_path = ?, is_watermarked = 1
                WHERE id = ?
            ''', (watermark_hash, watermarked_image_path, log_id))
            return cursor.rowcount > 0

    def get_access_logs(self, user_id: int = None, zone_id: int = None,
                        start_date: str = None, end_date: str = None,
                        access_type: str = None, limit: int = 100) -> List[Dict]:
        """
        Récupère les logs d'accès avec filtres optionnels.
        
        Args:
            user_id: Filtrer par utilisateur
            zone_id: Filtrer par zone
            start_date: Date de début (ISO format)
            end_date: Date de fin (ISO format)
            access_type: Type d'accès
            limit: Nombre maximum de résultats
            
        Returns:
            Liste des logs d'accès
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = '''
                SELECT al.*, u.username, u.full_name, az.name as zone_name
                FROM access_logs al
                LEFT JOIN users u ON al.user_id = u.id
                LEFT JOIN access_zones az ON al.zone_id = az.id
                WHERE 1=1
            '''
            params = []
            
            if user_id:
                query += ' AND al.user_id = ?'
                params.append(user_id)
            if zone_id:
                query += ' AND al.zone_id = ?'
                params.append(zone_id)
            if start_date:
                query += ' AND al.timestamp >= ?'
                params.append(start_date)
            if end_date:
                query += ' AND al.timestamp <= ?'
                params.append(end_date)
            if access_type:
                query += ' AND al.access_type = ?'
                params.append(access_type)
            
            query += ' ORDER BY al.timestamp DESC LIMIT ?'
            params.append(limit)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_log(self, log_id: int) -> Optional[Dict]:
        """Récupère un log spécifique par son ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT al.*, u.username, u.full_name, az.name as zone_name
                FROM access_logs al
                LEFT JOIN users u ON al.user_id = u.id
                LEFT JOIN access_zones az ON al.zone_id = az.id
                WHERE al.id = ?
            ''', (log_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # =========================================================================
    # GESTION DES ALERTES
    # =========================================================================

    def add_alert(self, log_id: int, alert_level: int, alert_type: str,
                  message: str = None) -> int:
        """Crée une nouvelle alerte."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO alerts (log_id, alert_level, alert_type, message)
                VALUES (?, ?, ?, ?)
            ''', (log_id, alert_level, alert_type, message))
            return cursor.lastrowid

    def acknowledge_alert(self, alert_id: int, user_id: int) -> bool:
        """Marque une alerte comme acquittée."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE alerts 
                SET is_acknowledged = 1, acknowledged_by = ?, acknowledged_at = ?
                WHERE id = ?
            ''', (user_id, datetime.now().isoformat(), alert_id))
            return cursor.rowcount > 0

    def get_pending_alerts(self) -> List[Dict]:
        """Récupère les alertes non acquittées."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.*, al.access_type, al.timestamp as access_time,
                       u.full_name as user_name
                FROM alerts a
                JOIN access_logs al ON a.log_id = al.id
                LEFT JOIN users u ON al.user_id = u.id
                WHERE a.is_acknowledged = 0
                ORDER BY a.alert_level DESC, a.created_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # STATISTIQUES
    # =========================================================================

    def get_statistics(self, days: int = 30) -> Dict:
        """Récupère les statistiques d'accès."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            stats = {}
            
            # Total des accès
            cursor.execute('''
                SELECT COUNT(*) as total FROM access_logs WHERE timestamp >= ?
            ''', (start_date,))
            stats['total_access'] = cursor.fetchone()['total']
            
            # Accès par type
            cursor.execute('''
                SELECT access_type, COUNT(*) as count FROM access_logs 
                WHERE timestamp >= ? GROUP BY access_type
            ''', (start_date,))
            stats['by_type'] = {row['access_type']: row['count'] 
                               for row in cursor.fetchall()}
            
            # Alertes non acquittées
            cursor.execute('SELECT COUNT(*) as count FROM alerts WHERE is_acknowledged = 0')
            stats['pending_alerts'] = cursor.fetchone()['count']
            
            # Utilisateurs actifs
            cursor.execute('SELECT COUNT(*) as count FROM users WHERE is_active = 1')
            stats['active_users'] = cursor.fetchone()['count']
            
            # Utilisateurs autorisés
            cursor.execute('''
                SELECT COUNT(*) as count FROM users 
                WHERE is_active = 1 AND is_authorized = 1
            ''')
            stats['authorized_users'] = cursor.fetchone()['count']
            
            return stats

    # =========================================================================
    # CONFORMITÉ RGPD
    # =========================================================================

    def anonymize_old_data(self, days: int = None) -> int:
        """Anonymise les données anciennes conformément au RGPD."""
        days = days or config.RGPD['anonymize_after_days']
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE access_logs 
                SET user_id = NULL, details = 'Données anonymisées (RGPD)'
                WHERE timestamp < ? AND user_id IS NOT NULL
            ''', (cutoff_date,))
            return cursor.rowcount

    def delete_old_logs(self, days: int = None) -> int:
        """Supprime les logs anciens conformément au RGPD."""
        days = days or config.RGPD['data_retention_days']
        cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM access_logs WHERE timestamp < ?', (cutoff_date,))
            return cursor.rowcount

    def export_user_data(self, user_id: int) -> Dict:
        """Exporte toutes les données d'un utilisateur (droit d'accès RGPD)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Données utilisateur
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            user_data = dict(cursor.fetchone()) if cursor.fetchone() else {}
            
            # Supprimer l'encodage facial binaire de l'export
            if 'face_encoding' in user_data:
                user_data['face_encoding'] = '[DONNÉES BIOMÉTRIQUES - Non exportables]'
            
            # Autorisations
            cursor.execute('''
                SELECT az.name, a.valid_from, a.valid_until, a.is_active
                FROM authorizations a
                JOIN access_zones az ON a.zone_id = az.id
                WHERE a.user_id = ?
            ''', (user_id,))
            user_data['authorizations'] = [dict(row) for row in cursor.fetchall()]
            
            # Logs d'accès
            cursor.execute('''
                SELECT timestamp, access_type, access_result
                FROM access_logs WHERE user_id = ?
            ''', (user_id,))
            user_data['access_logs'] = [dict(row) for row in cursor.fetchall()]
            
            return user_data


# Instance globale
db_manager = DatabaseManager()
