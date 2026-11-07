# -*- coding: utf-8 -*-
"""
Module de Notifications
=======================
Gestion des alertes et notifications par email (SMTP) et autres canaux.
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime
from typing import List, Optional, Dict, Any
import os
import threading
import queue
import logging

import config

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NotificationManager:
    """
    Gestionnaire de notifications multi-canaux.
    Supporte les emails SMTP avec pièces jointes.
    """

    def __init__(self):
        """Initialise le gestionnaire de notifications."""
        self.email_enabled = config.EMAIL['enabled']
        self.smtp_server = config.EMAIL['smtp_server']
        self.smtp_port = config.EMAIL['smtp_port']
        self.sender_email = config.EMAIL['sender_email']
        self.sender_password = config.EMAIL['sender_password']
        self.admin_emails = config.EMAIL['admin_emails']
        self.use_tls = config.EMAIL['use_tls']
        
        # File d'attente pour les notifications asynchrones
        self.notification_queue = queue.Queue()
        self.worker_thread = None
        self._stop_worker = False
        
        # Templates d'emails
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, str]:
        """Charge les templates d'emails."""
        return {
            'unauthorized_access': """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .alert {{ background-color: #ff4444; color: white; padding: 20px; border-radius: 5px; }}
        .warning {{ background-color: #ffbb33; color: black; padding: 20px; border-radius: 5px; }}
        .info {{ background-color: #33b5e5; color: white; padding: 20px; border-radius: 5px; }}
        .details {{ margin-top: 20px; padding: 15px; background-color: #f5f5f5; border-radius: 5px; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="alert">
        <h2>⚠️ ALERTE SÉCURITÉ - Accès Non Autorisé</h2>
    </div>
    <div class="details">
        <h3>Détails de l'incident:</h3>
        <ul>
            <li><strong>Date/Heure:</strong> {timestamp}</li>
            <li><strong>Type:</strong> {access_type}</li>
            <li><strong>Zone:</strong> {zone_name}</li>
            <li><strong>Utilisateur:</strong> {user_info}</li>
            <li><strong>Score de confiance:</strong> {confidence}%</li>
        </ul>
        <p><strong>Détails:</strong> {details}</p>
    </div>
    <div class="footer">
        <p>Ce message a été généré automatiquement par le Système de Contrôle d'Accès Biométrique.</p>
        <p>Veuillez ne pas répondre à cet email.</p>
    </div>
</body>
</html>
""",
            'impostor_alert': """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .critical {{ background-color: #cc0000; color: white; padding: 20px; border-radius: 5px; }}
        .details {{ margin-top: 20px; padding: 15px; background-color: #f5f5f5; border-radius: 5px; }}
        .capture {{ margin-top: 20px; text-align: center; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="critical">
        <h2>🚨 ALARME CRITIQUE - IMPOSTEUR DÉTECTÉ</h2>
    </div>
    <div class="details">
        <h3>Incident de sécurité majeur:</h3>
        <ul>
            <li><strong>Date/Heure:</strong> {timestamp}</li>
            <li><strong>Zone:</strong> {zone_name}</li>
            <li><strong>Action requise:</strong> Vérification immédiate</li>
        </ul>
        <p><strong>Description:</strong> Une personne non identifiée a tenté d'accéder à une zone sécurisée. 
        Une capture d'écran a été effectuée et jointe à ce message.</p>
    </div>
    <div class="capture">
        <p><em>Voir la capture en pièce jointe</em></p>
    </div>
    <div class="footer">
        <p>⚠️ ACTION IMMÉDIATE REQUISE</p>
        <p>Système de Contrôle d'Accès Biométrique</p>
    </div>
</body>
</html>
""",
            'daily_report': """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .header {{ background-color: #2196F3; color: white; padding: 20px; border-radius: 5px; }}
        .stats {{ margin-top: 20px; padding: 15px; background-color: #f5f5f5; border-radius: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background-color: #2196F3; color: white; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>📊 Rapport Quotidien - Contrôle d'Accès</h2>
        <p>Date: {date}</p>
    </div>
    <div class="stats">
        <h3>Statistiques du jour:</h3>
        <table>
            <tr><th>Métrique</th><th>Valeur</th></tr>
            <tr><td>Total des accès</td><td>{total_access}</td></tr>
            <tr><td>Accès autorisés</td><td>{authorized_access}</td></tr>
            <tr><td>Accès refusés</td><td>{denied_access}</td></tr>
            <tr><td>Alertes générées</td><td>{alerts_count}</td></tr>
            <tr><td>Utilisateurs actifs</td><td>{active_users}</td></tr>
        </table>
    </div>
    <div class="footer">
        <p>Rapport généré automatiquement par le Système de Contrôle d'Accès Biométrique.</p>
    </div>
</body>
</html>
""",
            'system_alert': """
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; }}
        .warning {{ background-color: #FF9800; color: white; padding: 20px; border-radius: 5px; }}
        .details {{ margin-top: 20px; padding: 15px; background-color: #f5f5f5; border-radius: 5px; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="warning">
        <h2>⚙️ Alerte Système</h2>
    </div>
    <div class="details">
        <h3>Information:</h3>
        <p><strong>Type:</strong> {alert_type}</p>
        <p><strong>Message:</strong> {message}</p>
        <p><strong>Date/Heure:</strong> {timestamp}</p>
    </div>
    <div class="footer">
        <p>Système de Contrôle d'Accès Biométrique</p>
    </div>
</body>
</html>
"""
        }

    def start_worker(self):
        """Démarre le worker de notifications asynchrones."""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self._stop_worker = False
            self.worker_thread = threading.Thread(target=self._notification_worker, daemon=True)
            self.worker_thread.start()
            logger.info("Worker de notifications démarré")

    def stop_worker(self):
        """Arrête le worker de notifications."""
        self._stop_worker = True
        if self.worker_thread:
            self.notification_queue.put(None)  # Signal d'arrêt
            self.worker_thread.join(timeout=5)
            logger.info("Worker de notifications arrêté")

    def _notification_worker(self):
        """Worker thread pour traiter les notifications en file d'attente."""
        while not self._stop_worker:
            try:
                notification = self.notification_queue.get(timeout=1)
                if notification is None:
                    break
                
                self._process_notification(notification)
                self.notification_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Erreur dans le worker de notifications: {e}")

    def _process_notification(self, notification: Dict):
        """Traite une notification de la file d'attente."""
        notification_type = notification.get('type')
        
        if notification_type == 'email':
            self._send_email_sync(
                recipients=notification.get('recipients'),
                subject=notification.get('subject'),
                body=notification.get('body'),
                html=notification.get('html'),
                attachments=notification.get('attachments')
            )

    def _send_email_sync(self, recipients: List[str], subject: str, 
                         body: str = None, html: str = None,
                         attachments: List[str] = None) -> bool:
        """
        Envoie un email de manière synchrone.
        
        Args:
            recipients: Liste des destinataires
            subject: Sujet de l'email
            body: Corps du message (texte brut)
            html: Corps du message (HTML)
            attachments: Liste des chemins vers les pièces jointes
            
        Returns:
            True si l'envoi a réussi
        """
        if not self.email_enabled:
            logger.warning("Service email désactivé")
            return False

        try:
            # Créer le message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(recipients)

            # Ajouter le corps du message
            if body:
                part_text = MIMEText(body, 'plain', 'utf-8')
                msg.attach(part_text)
            
            if html:
                part_html = MIMEText(html, 'html', 'utf-8')
                msg.attach(part_html)

            # Ajouter les pièces jointes
            if attachments:
                for filepath in attachments:
                    if os.path.exists(filepath):
                        with open(filepath, 'rb') as f:
                            img = MIMEImage(f.read())
                            img.add_header('Content-Disposition', 'attachment', 
                                          filename=os.path.basename(filepath))
                            msg.attach(img)

            # Connexion et envoi
            if self.use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls(context=context)
                    server.login(self.sender_email, self.sender_password)
                    server.sendmail(self.sender_email, recipients, msg.as_string())
            else:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                    server.login(self.sender_email, self.sender_password)
                    server.sendmail(self.sender_email, recipients, msg.as_string())

            logger.info(f"Email envoyé avec succès à {recipients}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de l'email: {e}")
            return False

    def send_email_async(self, recipients: List[str], subject: str,
                         body: str = None, html: str = None,
                         attachments: List[str] = None):
        """Envoie un email de manière asynchrone."""
        notification = {
            'type': 'email',
            'recipients': recipients,
            'subject': subject,
            'body': body,
            'html': html,
            'attachments': attachments
        }
        self.notification_queue.put(notification)

    # =========================================================================
    # ALERTES SPÉCIFIQUES
    # =========================================================================

    def send_unauthorized_access_alert(self, log_data: Dict, capture_path: str = None):
        """
        Envoie une alerte pour un accès non autorisé.
        
        Args:
            log_data: Données du log d'accès
            capture_path: Chemin vers la capture d'écran
        """
        subject = f"[ALERTE] Accès non autorisé - {log_data.get('access_type', 'N/A')}"
        
        html = self.templates['unauthorized_access'].format(
            timestamp=log_data.get('timestamp', datetime.now().isoformat()),
            access_type=log_data.get('access_type', 'N/A'),
            zone_name=log_data.get('zone_name', 'Zone principale'),
            user_info=log_data.get('full_name', log_data.get('user_id', 'Inconnu')),
            confidence=log_data.get('confidence_score', 0),
            details=log_data.get('details', 'Aucun détail disponible')
        )
        
        attachments = [capture_path] if capture_path and os.path.exists(capture_path) else None
        
        self.send_email_async(
            recipients=self.admin_emails,
            subject=subject,
            html=html,
            attachments=attachments
        )
        
        logger.info(f"Alerte d'accès non autorisé envoyée: {log_data.get('access_type')}")

    def send_impostor_alert(self, log_data: Dict, capture_path: str):
        """
        Envoie une alerte critique pour un imposteur détecté.
        
        Args:
            log_data: Données du log d'accès
            capture_path: Chemin vers la capture d'écran
        """
        subject = "🚨 [ALARME CRITIQUE] Imposteur détecté - Action immédiate requise"
        
        html = self.templates['impostor_alert'].format(
            timestamp=log_data.get('timestamp', datetime.now().isoformat()),
            zone_name=log_data.get('zone_name', 'Zone principale')
        )
        
        attachments = [capture_path] if capture_path and os.path.exists(capture_path) else None
        
        self.send_email_async(
            recipients=self.admin_emails,
            subject=subject,
            html=html,
            attachments=attachments
        )
        
        logger.warning("Alerte imposteur critique envoyée!")

    def send_daily_report(self, stats: Dict):
        """
        Envoie le rapport quotidien.
        
        Args:
            stats: Statistiques du jour
        """
        subject = f"[Rapport] Contrôle d'accès - {datetime.now().strftime('%Y-%m-%d')}"
        
        html = self.templates['daily_report'].format(
            date=datetime.now().strftime('%Y-%m-%d'),
            total_access=stats.get('total_access', 0),
            authorized_access=stats.get('by_type', {}).get('AUTHORIZED', 0),
            denied_access=stats.get('by_type', {}).get('KNOWN_UNAUTHORIZED', 0) + 
                          stats.get('by_type', {}).get('IMPOSTOR', 0),
            alerts_count=stats.get('pending_alerts', 0),
            active_users=stats.get('active_users', 0)
        )
        
        self.send_email_async(
            recipients=self.admin_emails,
            subject=subject,
            html=html
        )
        
        logger.info("Rapport quotidien envoyé")

    def send_system_alert(self, alert_type: str, message: str):
        """
        Envoie une alerte système.
        
        Args:
            alert_type: Type d'alerte
            message: Message de l'alerte
        """
        subject = f"[Système] {alert_type}"
        
        html = self.templates['system_alert'].format(
            alert_type=alert_type,
            message=message,
            timestamp=datetime.now().isoformat()
        )
        
        self.send_email_async(
            recipients=self.admin_emails,
            subject=subject,
            html=html
        )

    # =========================================================================
    # NOTIFICATIONS LOCALES
    # =========================================================================

    def show_local_notification(self, title: str, message: str, 
                                notification_type: str = 'info'):
        """
        Affiche une notification locale (placeholder pour intégration système).
        
        Args:
            title: Titre de la notification
            message: Message de la notification
            notification_type: Type (info, warning, error, critical)
        """
        # Cette méthode peut être étendue pour utiliser des notifications système
        # (Windows Toast, Linux notify-send, etc.)
        logger.info(f"[{notification_type.upper()}] {title}: {message}")

    def play_alert_sound(self, alert_level: int):
        """
        Joue un son d'alerte selon le niveau.
        
        Args:
            alert_level: Niveau d'alerte (0-3)
        """
        # Placeholder pour l'intégration de sons d'alerte
        # Peut utiliser winsound sur Windows, pygame, ou playsound
        try:
            if alert_level >= config.ALERT_LEVELS['ALARM']:
                # Son d'alarme critique
                import winsound
                winsound.Beep(1000, 500)
                winsound.Beep(1500, 500)
                winsound.Beep(1000, 500)
            elif alert_level >= config.ALERT_LEVELS['CRITICAL']:
                import winsound
                winsound.Beep(800, 300)
                winsound.Beep(800, 300)
            elif alert_level >= config.ALERT_LEVELS['WARNING']:
                import winsound
                winsound.Beep(600, 200)
        except ImportError:
            logger.warning("Module winsound non disponible")
        except Exception as e:
            logger.error(f"Erreur lors de la lecture du son: {e}")


class AlertManager:
    """
    Gestionnaire d'alertes intégré au système.
    Coordonne les notifications et les actions de sécurité.
    """

    def __init__(self, notification_manager: NotificationManager = None):
        """
        Initialise le gestionnaire d'alertes.
        
        Args:
            notification_manager: Instance du gestionnaire de notifications
        """
        self.notification_manager = notification_manager or NotificationManager()
        self.alert_history = []
        self.max_history = 1000

    def trigger_alert(self, access_type: str, log_data: Dict, 
                      capture_path: str = None) -> Dict:
        """
        Déclenche une alerte selon le type d'accès.
        
        Args:
            access_type: Type d'accès (AUTHORIZED, KNOWN_UNAUTHORIZED, IMPOSTOR, UNKNOWN)
            log_data: Données du log
            capture_path: Chemin vers la capture
            
        Returns:
            Informations sur l'alerte déclenchée
        """
        alert_info = {
            'timestamp': datetime.now().isoformat(),
            'access_type': access_type,
            'log_data': log_data,
            'actions_taken': []
        }

        if access_type == 'AUTHORIZED':
            # Accès normal, pas d'alerte critique
            alert_info['level'] = config.ALERT_LEVELS['INFO']
            alert_info['actions_taken'].append('log_only')
            
        elif access_type == 'KNOWN_UNAUTHORIZED':
            # Utilisateur connu mais non autorisé
            alert_info['level'] = config.ALERT_LEVELS['WARNING']
            self.notification_manager.send_unauthorized_access_alert(log_data, capture_path)
            self.notification_manager.play_alert_sound(config.ALERT_LEVELS['WARNING'])
            self.notification_manager.show_local_notification(
                "Accès Refusé",
                f"Utilisateur {log_data.get('full_name', 'connu')} - Accès refusé",
                'warning'
            )
            alert_info['actions_taken'].extend(['email_sent', 'sound_played', 'local_notification'])
            
        elif access_type == 'IMPOSTOR':
            # Imposteur détecté - alerte maximale
            alert_info['level'] = config.ALERT_LEVELS['ALARM']
            self.notification_manager.send_impostor_alert(log_data, capture_path)
            self.notification_manager.play_alert_sound(config.ALERT_LEVELS['ALARM'])
            self.notification_manager.show_local_notification(
                "ALARME - IMPOSTEUR",
                "Tentative d'intrusion détectée!",
                'critical'
            )
            alert_info['actions_taken'].extend(['email_sent', 'alarm_triggered', 'capture_saved'])
            
        elif access_type == 'UNKNOWN':
            # Personne inconnue
            alert_info['level'] = config.ALERT_LEVELS['CRITICAL']
            self.notification_manager.send_unauthorized_access_alert(log_data, capture_path)
            self.notification_manager.play_alert_sound(config.ALERT_LEVELS['CRITICAL'])
            alert_info['actions_taken'].extend(['email_sent', 'sound_played'])

        # Ajouter à l'historique
        self.alert_history.append(alert_info)
        if len(self.alert_history) > self.max_history:
            self.alert_history = self.alert_history[-self.max_history:]

        return alert_info

    def get_recent_alerts(self, count: int = 10) -> List[Dict]:
        """Récupère les alertes récentes."""
        return self.alert_history[-count:]


# Instances globales
notification_manager = NotificationManager()
alert_manager = AlertManager(notification_manager)
