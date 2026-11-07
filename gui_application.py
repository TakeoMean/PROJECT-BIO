# -*- coding: utf-8 -*-
"""
Interface Graphique du Système de Contrôle d'Accès Biométrique
==============================================================
Application Tkinter complète pour la gestion du contrôle d'accès.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from tkinter import font as tkfont
import cv2
from PIL import Image, ImageTk
import threading
import time
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import pickle
import os

import config
from database import db_manager
from face_recognition_module import face_recognizer
from watermark_module import watermark_manager
from notification_module import notification_manager, alert_manager


class AccessControlApp:
    """Application principale de contrôle d'accès biométrique."""

    def __init__(self, root: tk.Tk):
        """
        Initialise l'application.
        
        Args:
            root: Fenêtre Tkinter principale
        """
        self.root = root
        self.root.title(config.UI['window_title'])
        self.root.geometry(config.UI['window_size'])
        self.root.minsize(1000, 700)

        self.theme = {
            'bg': '#f2f4f7',
            'surface': '#ffffff',
            'surface_alt': '#f7f9fb',
            'border': '#dce1e8',
            'text': '#1d232b',
            'muted': '#6b7280',
            'accent': '#0e4d92',
            'accent_soft': '#e1ecf8',
            'accent_2': '#0f766e',
            'success': '#2f9e44',
            'warning': '#f08c00',
            'danger': '#d9480f',
            'header_start': '#0e4d92',
            'header_end': '#0f766e',
            'header_text': '#f8fafc',
            'header_pill_bg': '#f8fafc'
        }

        self.fonts = {
            'title': tkfont.Font(family='Bahnschrift', size=20, weight='bold'),
            'subtitle': tkfont.Font(family='Candara', size=11),
            'body': tkfont.Font(family='Candara', size=10),
            'body_bold': tkfont.Font(family='Candara', size=10, weight='bold'),
            'header': tkfont.Font(family='Bahnschrift', size=12, weight='bold'),
            'stat': tkfont.Font(family='Bahnschrift', size=22, weight='bold'),
            'big': tkfont.Font(family='Bahnschrift', size=16, weight='bold'),
            'mono': tkfont.Font(family='Cascadia Mono', size=9)
        }
        
        # État de l'application
        self.camera = None
        self.camera_active = False
        self.recognition_active = False
        self.current_frame = None
        self.current_zone_id = 1  # Zone par défaut

        self._recognition_busy = False
        self._pending_results = None
        self._results_lock = threading.Lock()
        self._last_annotated_frame = None
        self._last_result_time = 0
        self._pulse_state = False
        
        # Dictionnaire des noms d'utilisateurs pour l'affichage
        self.users_info = {}
        self._load_users_info()
        
        # Configuration du style
        self._setup_styles()
        
        # Création de l'interface
        self._create_menu()
        self._create_main_layout()

        self._update_live_indicator()
        
        # Démarrer le worker de notifications
        notification_manager.start_worker()
        
        # Mise à jour périodique
        self._update_status_bar()
        
        # Gérer la fermeture
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _setup_styles(self):
        """Configure les styles de l'interface."""
        style = ttk.Style()
        style.theme_use('clam')

        self.root.configure(bg=self.theme['bg'])

        style.configure('TFrame', background=self.theme['bg'])
        style.configure('App.TFrame', background=self.theme['bg'])
        style.configure('Card.TFrame', background=self.theme['surface'])

        style.configure('TLabel', background=self.theme['surface'], foreground=self.theme['text'],
                        font=self.fonts['body'])
        style.configure('Muted.TLabel', background=self.theme['surface'], foreground=self.theme['muted'],
                        font=self.fonts['body'])
        style.configure('Header.TLabel', background=self.theme['surface'], foreground=self.theme['text'],
                        font=self.fonts['header'])
        style.configure('Success.TLabel', background=self.theme['surface'],
                        foreground=self.theme['success'], font=self.fonts['body_bold'])
        style.configure('Warning.TLabel', background=self.theme['surface'],
                        foreground=self.theme['warning'], font=self.fonts['body_bold'])
        style.configure('Danger.TLabel', background=self.theme['surface'],
                        foreground=self.theme['danger'], font=self.fonts['body_bold'])

        style.configure('Card.TLabelframe', background=self.theme['surface'],
                        bordercolor=self.theme['border'], relief='ridge', padding=12)
        style.configure('Card.TLabelframe.Label', background=self.theme['surface'],
                        foreground=self.theme['text'], font=self.fonts['header'])

        style.configure('TButton', font=self.fonts['body_bold'], padding=8, relief='flat')
        style.configure('Primary.TButton', background=self.theme['accent'], foreground='#ffffff',
                        font=self.fonts['body_bold'], padding=10)
        style.configure('Big.TButton', font=self.fonts['body_bold'], padding=10)
        style.map('Primary.TButton',
                  background=[('active', self.theme['accent_2']), ('disabled', self.theme['accent_soft'])],
                  foreground=[('disabled', self.theme['muted'])])

        style.configure('App.TNotebook', background=self.theme['bg'], borderwidth=0)
        style.configure('App.TNotebook.Tab',
                        background=self.theme['surface_alt'],
                        foreground=self.theme['text'],
                        font=self.fonts['body_bold'],
                        padding=(14, 8))
        style.map('App.TNotebook.Tab',
                  background=[('selected', self.theme['surface'])],
                  foreground=[('selected', self.theme['text'])])

        style.configure('Treeview',
                        background=self.theme['surface'],
                        fieldbackground=self.theme['surface'],
                        foreground=self.theme['text'],
                        rowheight=24,
                        font=self.fonts['body'])
        style.configure('Treeview.Heading', font=self.fonts['body_bold'])
        style.map('Treeview',
                  background=[('selected', self.theme['accent_soft'])],
                  foreground=[('selected', self.theme['text'])])

        style.configure('Video.TLabel', background=self.theme['surface_alt'])
        style.configure('SpoofingIdle.TProgressbar',
                troughcolor=self.theme['surface_alt'],
                background=self.theme['accent_2'])
        style.configure('SpoofingOk.TProgressbar',
                troughcolor=self.theme['surface_alt'],
                background=self.theme['success'])
        style.configure('SpoofingBad.TProgressbar',
                troughcolor=self.theme['surface_alt'],
                background=self.theme['danger'])

        base_layout = style.layout('Horizontal.TProgressbar')
        style.layout('SpoofingIdle.TProgressbar', base_layout)
        style.layout('SpoofingOk.TProgressbar', base_layout)
        style.layout('SpoofingBad.TProgressbar', base_layout)

    def _load_users_info(self):
        """Charge les informations des utilisateurs."""
        users = db_manager.get_all_users()
        self.users_info = {u['id']: u['full_name'] for u in users}

    def _create_menu(self):
        """Crée la barre de menu."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Menu Fichier
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Fichier", menu=file_menu)
        file_menu.add_command(label="Exporter les logs", command=self._export_logs)
        file_menu.add_command(label="Importer des visages", command=self._import_faces)
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", command=self._on_closing)
        
        # Menu Utilisateurs
        user_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Utilisateurs", menu=user_menu)
        user_menu.add_command(label="Ajouter un utilisateur", command=self._add_user_dialog)
        user_menu.add_command(label="Gérer les utilisateurs", command=self._manage_users_dialog)
        user_menu.add_command(label="Entraîner le modèle", command=self._train_model)
        
        # Menu Tatouage
        watermark_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tatouage", menu=watermark_menu)
        watermark_menu.add_command(label="Vérifier un log", command=self._verify_watermark_dialog)
        watermark_menu.add_command(label="Test de robustesse", command=self._test_robustness_dialog)
        
        # Menu Aide
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Aide", menu=help_menu)
        help_menu.add_command(label="À propos", command=self._show_about)
        help_menu.add_command(label="Documentation", command=self._show_documentation)

    def _create_header(self, parent: tk.Widget):
        """Crée l'en-tête avec un fond dégradé."""
        header_container = tk.Frame(parent, bg=self.theme['bg'])
        header_container.pack(fill=tk.X, padx=12, pady=(12, 8))

        self.header_canvas = tk.Canvas(
            header_container,
            height=90,
            highlightthickness=0,
            bd=0,
            bg=self.theme['header_end']
        )
        self.header_canvas.pack(fill=tk.X, expand=True)
        self.header_canvas.bind('<Configure>', self._draw_header_gradient)

        self.header_content = tk.Frame(self.header_canvas, bg=self.theme['header_end'])
        self.header_window = self.header_canvas.create_window(
            (0, 0), anchor='nw', window=self.header_content
        )

        title = tk.Label(
            self.header_content,
            text="Contrôle d'Accès Biométrique",
            font=self.fonts['title'],
            fg=self.theme['header_text'],
            bg=self.theme['header_end']
        )
        subtitle = tk.Label(
            self.header_content,
            text="Reconnaissance faciale, anti-spoofing et intégrité des logs",
            font=self.fonts['subtitle'],
            fg=self.theme['header_text'],
            bg=self.theme['header_end']
        )

        status_container = tk.Frame(self.header_content, bg=self.theme['header_end'])
        self.header_camera_status = tk.Label(
            status_container,
            text="Caméra: Inactive",
            font=self.fonts['body_bold'],
            fg=self.theme['text'],
            bg=self.theme['header_pill_bg'],
            padx=12, pady=6,
            bd=1, relief='solid'
        )
        self.header_recognition_status = tk.Label(
            status_container,
            text="Reconnaissance: Inactive",
            font=self.fonts['body_bold'],
            fg=self.theme['text'],
            bg=self.theme['header_pill_bg'],
            padx=12, pady=6,
            bd=1, relief='solid'
        )

        title.grid(row=0, column=0, sticky='w')
        subtitle.grid(row=1, column=0, sticky='w', pady=(4, 0))
        status_container.grid(row=0, column=1, rowspan=2, sticky='e', padx=(20, 0))
        self.header_camera_status.pack(side=tk.LEFT, padx=6)
        self.header_recognition_status.pack(side=tk.LEFT, padx=6)

        self.header_content.grid_columnconfigure(0, weight=1)
        self.header_content.grid_columnconfigure(1, weight=0)

    def _draw_header_gradient(self, event):
        """Dessine un dégradé horizontal dans l'en-tête."""
        self.header_canvas.delete('gradient')
        width = max(event.width, 1)
        height = max(event.height, 1)

        start_r, start_g, start_b = self._hex_to_rgb(self.theme['header_start'])
        end_r, end_g, end_b = self._hex_to_rgb(self.theme['header_end'])

        for i in range(width):
            ratio = i / width
            r = int(start_r + (end_r - start_r) * ratio)
            g = int(start_g + (end_g - start_g) * ratio)
            b = int(start_b + (end_b - start_b) * ratio)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.header_canvas.create_line(i, 0, i, height, fill=color, tags='gradient')

        self.header_canvas.coords(self.header_window, 16, 12)

    def _hex_to_rgb(self, color: str) -> Tuple[int, int, int]:
        """Convertit une couleur hex en tuple RGB."""
        color = color.lstrip('#')
        return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)

    def _create_main_layout(self):
        """Crée la disposition principale de l'interface."""
        # Frame principale avec en-tête et notebook
        self.main_container = ttk.Frame(self.root, style='App.TFrame')
        self.main_container.pack(fill=tk.BOTH, expand=True)

        self._create_header(self.main_container)

        self.notebook = ttk.Notebook(self.main_container, style='App.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        
        # Onglet Contrôle d'accès
        self.access_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.access_frame, text="Contrôle d'Accès")
        self._create_access_tab()
        
        # Onglet Gestion des utilisateurs
        self.users_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.users_frame, text="Utilisateurs")
        self._create_users_tab()
        
        # Onglet Historique
        self.history_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.history_frame, text="Historique")
        self._create_history_tab()
        
        # Onglet Alertes
        self.alerts_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.alerts_frame, text="Alertes")
        self._create_alerts_tab()
        
        # Onglet Statistiques
        self.stats_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.stats_frame, text="Statistiques")
        self._create_stats_tab()
        
        # Barre de statut
        self._create_status_bar()

    def _create_access_tab(self):
        """Crée l'onglet de contrôle d'accès."""
        # Frame gauche - Caméra
        left_frame = ttk.Frame(self.access_frame, style='Card.TFrame')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 6), pady=6)

        camera_card = ttk.LabelFrame(left_frame, text="Flux Caméra", style='Card.TLabelframe')
        camera_card.pack(fill=tk.BOTH, expand=True)

        self.video_label = ttk.Label(camera_card, text="Caméra inactive", style='Video.TLabel')
        self.video_label.pack(fill=tk.BOTH, expand=True, pady=(2, 10))

        btn_frame = ttk.Frame(camera_card, style='Card.TFrame')
        btn_frame.pack(fill=tk.X, pady=6)

        self.btn_camera = ttk.Button(
            btn_frame,
            text="Démarrer Caméra",
            command=self._toggle_camera,
            style='Primary.TButton'
        )
        self.btn_camera.pack(side=tk.LEFT, padx=5)

        self.btn_recognition = ttk.Button(
            btn_frame,
            text="Activer Reconnaissance",
            command=self._toggle_recognition,
            style='Big.TButton',
            state=tk.DISABLED
        )
        self.btn_recognition.pack(side=tk.LEFT, padx=5)

        self.live_indicator = tk.Label(
            btn_frame,
            text="● LIVE",
            font=self.fonts['body_bold'],
            fg=self.theme['muted'],
            bg=self.theme['surface']
        )
        self.live_indicator.pack(side=tk.RIGHT, padx=6)

        # Frame droite - Informations
        right_frame = ttk.Frame(self.access_frame, style='Card.TFrame')
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(6, 8), pady=6)

        zone_card = ttk.LabelFrame(right_frame, text="Zone & Statut", style='Card.TLabelframe')
        zone_card.pack(fill=tk.X, pady=(0, 8))

        zone_frame = ttk.Frame(zone_card, style='Card.TFrame')
        zone_frame.pack(fill=tk.X, pady=4)
        ttk.Label(zone_frame, text="Zone:", style='Muted.TLabel').pack(side=tk.LEFT)
        self.zone_combo = ttk.Combobox(zone_frame, state='readonly', width=25)
        self.zone_combo.pack(side=tk.LEFT, padx=10)
        self._refresh_zones()

        self.status_frame = ttk.Frame(zone_card, style='Card.TFrame')
        self.status_frame.pack(fill=tk.X, pady=6)

        self.status_icon = ttk.Label(self.status_frame, text="●", font=self.fonts['header'])
        self.status_icon.pack(side=tk.LEFT)
        self.status_text = ttk.Label(self.status_frame, text="En attente...", style='Header.TLabel')
        self.status_text.pack(side=tk.LEFT, padx=10)

        self.person_frame = ttk.LabelFrame(right_frame, text="Personne détectée", style='Card.TLabelframe')
        self.person_frame.pack(fill=tk.X, pady=8)

        self.person_photo = ttk.Label(self.person_frame)
        self.person_photo.pack()

        self.person_name = ttk.Label(self.person_frame, text="-", style='Header.TLabel')
        self.person_name.pack()

        self.person_details = ttk.Label(self.person_frame, text="", style='Muted.TLabel')
        self.person_details.pack()

        self.confidence_label = ttk.Label(self.person_frame, text="", style='Muted.TLabel')
        self.confidence_label.pack()

        self.spoofing_frame = ttk.LabelFrame(right_frame, text="Anti-Spoofing", style='Card.TLabelframe')
        self.spoofing_frame.pack(fill=tk.X, pady=8)

        self.spoofing_status = ttk.Label(self.spoofing_frame, text="Non vérifiée", style='Muted.TLabel')
        self.spoofing_status.pack()

        self.spoofing_confidence = ttk.Label(self.spoofing_frame, text="", style='Muted.TLabel')
        self.spoofing_confidence.pack()

        self.spoofing_meter = ttk.Progressbar(
            self.spoofing_frame,
            mode='determinate',
            length=240,
            style='SpoofingIdle.TProgressbar'
        )
        self.spoofing_meter.pack(pady=6)

        self.spoofing_details = ttk.Label(
            self.spoofing_frame,
            text="",
            style='Muted.TLabel',
            wraplength=300,
            justify=tk.LEFT
        )
        self.spoofing_details.pack(pady=4)

        logs_card = ttk.LabelFrame(right_frame, text="Derniers accès", style='Card.TLabelframe')
        logs_card.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.recent_logs_list = tk.Listbox(
            logs_card,
            height=8,
            font=self.fonts['mono'],
            bg=self.theme['surface'],
            fg=self.theme['text'],
            selectbackground=self.theme['accent_soft'],
            selectforeground=self.theme['text'],
            highlightthickness=0
        )
        self.recent_logs_list.pack(fill=tk.BOTH, expand=True)
        self._refresh_recent_logs()

    def _create_users_tab(self):
        """Crée l'onglet de gestion des utilisateurs."""
        # Barre d'outils
        toolbar = ttk.Frame(self.users_frame)
        toolbar.pack(fill=tk.X, pady=5)
        
        ttk.Button(toolbar, text="➕ Ajouter", command=self._add_user_dialog).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="✏️ Modifier", command=self._edit_user).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🗑️ Supprimer", command=self._delete_user).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="📷 Enregistrer visage", command=self._register_face).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="🔄 Actualiser", command=self._refresh_users_list).pack(side=tk.LEFT, padx=2)
        
        # Liste des utilisateurs
        columns = ('ID', 'Nom', 'Email', 'Département', 'Rôle', 'Autorisé', 'Visage')
        self.users_tree = ttk.Treeview(self.users_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            self.users_tree.heading(col, text=col)
            self.users_tree.column(col, width=100)
        
        self.users_tree.column('ID', width=50)
        self.users_tree.column('Nom', width=150)
        self.users_tree.column('Email', width=180)
        
        scrollbar = ttk.Scrollbar(self.users_frame, orient=tk.VERTICAL, command=self.users_tree.yview)
        self.users_tree.configure(yscrollcommand=scrollbar.set)
        
        self.users_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self._refresh_users_list()

    def _create_history_tab(self):
        """Crée l'onglet d'historique des accès."""
        # Filtres
        filter_frame = ttk.LabelFrame(self.history_frame, text="Filtres & Recherche", padding=10, style='Card.TLabelframe')
        filter_frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Ligne 1 des filtres
        row1 = ttk.Frame(filter_frame)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="Type d'accès:").pack(side=tk.LEFT)
        self.filter_type = ttk.Combobox(row1, values=[
            'Tous',
            'AUTHORIZED - ✅ Autorisé(e)',
            'UNKNOWN - ❓ Non enregistré(e)',
            'KNOWN_UNAUTHORIZED - ⚠️ Enregistré(e) mais refusé(e)',
            'IMPOSTOR - 🚨 Usurpation détectée'
        ], width=45)
        self.filter_type.set('Tous')
        self.filter_type.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(row1, text="🔍 Rechercher", command=self._search_logs).pack(side=tk.LEFT, padx=20)
        ttk.Button(row1, text="🔄 Réinitialiser", command=self._reset_log_filters).pack(side=tk.LEFT)
        
        # Liste des logs
        columns = ('ID', 'Date/Heure', 'Utilisateur', 'Type', 'Résultat', 'Confiance', 'Tatoué')
        self.logs_tree = ttk.Treeview(self.history_frame, columns=columns, show='headings', height=20)
        
        for col in columns:
            self.logs_tree.heading(col, text=col)
            self.logs_tree.column(col, width=100)
        
        self.logs_tree.column('ID', width=50)
        self.logs_tree.column('Date/Heure', width=150)
        self.logs_tree.column('Utilisateur', width=150)
        
        # Menu contextuel
        self.log_context_menu = tk.Menu(self.logs_tree, tearoff=0)
        self.log_context_menu.add_command(label="Voir détails", command=self._view_log_details)
        self.log_context_menu.add_command(label="Vérifier tatouage", command=self._verify_log_watermark)
        self.log_context_menu.add_command(label="Voir capture", command=self._view_capture)
        
        self.logs_tree.bind("<Button-3>", self._show_log_context_menu)
        
        scrollbar = ttk.Scrollbar(self.history_frame, orient=tk.VERTICAL, command=self.logs_tree.yview)
        self.logs_tree.configure(yscrollcommand=scrollbar.set)
        
        self.logs_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        self._refresh_logs_list()

    def _create_alerts_tab(self):
        """Crée l'onglet des alertes."""
        # En-tête
        header = ttk.Frame(self.alerts_frame, style='Card.TFrame')
        header.pack(fill=tk.X, pady=5, padx=5)
        
        ttk.Label(header, text="Alertes en attente", style='Header.TLabel').pack(side=tk.LEFT)
        ttk.Button(header, text="✓ Acquitter sélection", 
                   command=self._acknowledge_selected_alert).pack(side=tk.RIGHT)
        ttk.Button(header, text="🔄 Actualiser", 
                   command=self._refresh_alerts).pack(side=tk.RIGHT, padx=5)
        
        # Liste des alertes
        columns = ('ID', 'Date/Heure', 'Niveau', 'Type', 'Message', 'Utilisateur')
        self.alerts_tree = ttk.Treeview(self.alerts_frame, columns=columns, show='headings', height=15)
        
        for col in columns:
            self.alerts_tree.heading(col, text=col)
            self.alerts_tree.column(col, width=120)
        
        self.alerts_tree.column('ID', width=50)
        self.alerts_tree.column('Message', width=250)
        
        scrollbar = ttk.Scrollbar(self.alerts_frame, orient=tk.VERTICAL, command=self.alerts_tree.yview)
        self.alerts_tree.configure(yscrollcommand=scrollbar.set)
        
        self.alerts_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        # Tags pour colorer les alertes
        self.alerts_tree.tag_configure('critical', background='#ffcccc')
        self.alerts_tree.tag_configure('warning', background='#fff3cd')
        self.alerts_tree.tag_configure('info', background='#cce5ff')
        
        self._refresh_alerts()

    def _create_stats_tab(self):
        """Crée l'onglet des statistiques."""
        # Frame pour les statistiques
        stats_container = ttk.Frame(self.stats_frame, style='Card.TFrame')
        stats_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Cartes de statistiques
        cards_frame = ttk.Frame(stats_container, style='Card.TFrame')
        cards_frame.pack(fill=tk.X, pady=10)
        
        self.stat_cards = {}
        card_configs = [
            ('total_access', 'Total Accès (30j)', '#2196F3'),
            ('authorized', 'Autorisés', '#4CAF50'),
            ('denied', 'Refusés', '#FF9800'),
            ('alerts', 'Alertes', '#f44336'),
            ('users', 'Utilisateurs', '#9C27B0')
        ]
        
        for key, title, color in card_configs:
            card = ttk.LabelFrame(cards_frame, text=title, padding=15, style='Card.TLabelframe')
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
            
            value_label = ttk.Label(card, text="0", font=self.fonts['stat'])
            value_label.pack()
            
            self.stat_cards[key] = value_label
        
        # Bouton d'actualisation
        ttk.Button(stats_container, text="🔄 Actualiser les statistiques", 
                   command=self._refresh_stats).pack(pady=10)
        
        # Zone d'affichage des détails
        details_frame = ttk.LabelFrame(stats_container, text="Détails", padding=10, style='Card.TLabelframe')
        details_frame.pack(fill=tk.BOTH, expand=True)
        
        self.stats_text = tk.Text(
            details_frame,
            height=15,
            font=self.fonts['mono'],
            bg=self.theme['surface'],
            fg=self.theme['text'],
            relief='flat'
        )
        self.stats_text.pack(fill=tk.BOTH, expand=True)
        
        self._refresh_stats()

    def _create_status_bar(self):
        """Crée la barre de statut."""
        self.status_bar = ttk.Frame(self.main_container, style='App.TFrame')
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM, padx=12, pady=(0, 12))
        
        ttk.Separator(self.status_bar, orient=tk.HORIZONTAL).pack(fill=tk.X)
        
        bar_frame = ttk.Frame(self.status_bar)
        bar_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.camera_status = ttk.Label(bar_frame, text="📷 Caméra: Inactive", style='Muted.TLabel')
        self.camera_status.pack(side=tk.LEFT)
        
        ttk.Separator(bar_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        
        self.recognition_status = ttk.Label(bar_frame, text="🔍 Reconnaissance: Inactive", style='Muted.TLabel')
        self.recognition_status.pack(side=tk.LEFT)
        
        ttk.Separator(bar_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)
        
        self.db_status = ttk.Label(bar_frame, text="💾 BD: Connectée", style='Muted.TLabel')
        self.db_status.pack(side=tk.LEFT)
        
        self.datetime_label = ttk.Label(bar_frame, text="", style='Muted.TLabel')
        self.datetime_label.pack(side=tk.RIGHT)

    def _update_status_bar(self):
        """Met à jour la barre de statut."""
        self.datetime_label.config(text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        self._sync_status_badges()
        self.root.after(1000, self._update_status_bar)

    def _sync_status_badges(self):
        """Synchronise les badges d'état dans l'en-tête."""
        cam_text = "Caméra: Active" if self.camera_active else "Caméra: Inactive"
        rec_text = "Reconnaissance: Active" if self.recognition_active else "Reconnaissance: Inactive"

        cam_color = self.theme['accent'] if self.camera_active else self.theme['muted']
        rec_color = self.theme['accent_2'] if self.recognition_active else self.theme['muted']
        cam_bg = self.theme['accent_soft'] if self.camera_active else self.theme['header_pill_bg']
        rec_bg = self.theme['accent_soft'] if self.recognition_active else self.theme['header_pill_bg']

        self.header_camera_status.config(text=cam_text, fg=cam_color, bg=cam_bg)
        self.header_recognition_status.config(text=rec_text, fg=rec_color, bg=rec_bg)

    def _update_live_indicator(self):
        """Anime le badge LIVE quand la caméra est active."""
        if hasattr(self, 'live_indicator'):
            if self.camera_active:
                self._pulse_state = not self._pulse_state
                color = self.theme['accent_2'] if self._pulse_state else self.theme['accent']
            else:
                color = self.theme['muted']
            self.live_indicator.config(fg=color)

        self.root.after(500, self._update_live_indicator)

    # =========================================================================
    # CONTRÔLE DE LA CAMÉRA
    # =========================================================================

    def _toggle_camera(self):
        """Active/désactive la caméra."""
        if self.camera_active:
            self._stop_camera()
        else:
            self._start_camera()

    def _start_camera(self):
        """Démarre la caméra."""
        try:
            self.camera = cv2.VideoCapture(config.UI.get('camera_index', 0))
            if not self.camera.isOpened():
                raise Exception("Impossible d'ouvrir la caméra")
            
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, config.UI['camera_width'])
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, config.UI['camera_height'])
            
            self.camera_active = True
            self.btn_camera.config(text="Arrêter Caméra")
            self.btn_recognition.config(state=tk.NORMAL)
            self.camera_status.config(text="📷 Caméra: Active")
            self._sync_status_badges()
            
            self._update_camera()
            
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur caméra: {e}")

    def _stop_camera(self):
        """Arrête la caméra."""
        self.camera_active = False
        self.recognition_active = False
        
        if self.camera:
            self.camera.release()
            self.camera = None
        
        self.btn_camera.config(text="Démarrer Caméra")
        self.btn_recognition.config(state=tk.DISABLED, text="Activer Reconnaissance")
        self.camera_status.config(text="📷 Caméra: Inactive")
        self.recognition_status.config(text="🔍 Reconnaissance: Inactive")
        self.video_label.config(image='', text="Caméra inactive")
        with self._results_lock:
            self._pending_results = None
        self._sync_status_badges()

    def _update_camera(self):
        """Met à jour l'affichage de la caméra."""
        if not self.camera_active or not self.camera:
            return
        
        ret, frame = self.camera.read()
        if ret:
            self.current_frame = frame.copy()

            if self.recognition_active:
                if not self._recognition_busy:
                    self._recognition_busy = True
                    threading.Thread(
                        target=self._recognition_worker,
                        args=(frame.copy(),),
                        daemon=True
                    ).start()

                pending = None
                with self._results_lock:
                    if self._pending_results:
                        pending = self._pending_results
                        self._pending_results = None

                if pending:
                    pending_frame, results = pending
                    annotated = self._apply_recognition_results(pending_frame, results)
                    self._last_annotated_frame = annotated
                    self._last_result_time = time.time()

                if self._last_annotated_frame is not None:
                    if time.time() - self._last_result_time < 3.0:  # Show for 3 seconds
                        frame = self._last_annotated_frame
            else:
                self._last_annotated_frame = None

            # Convertir pour Tkinter
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            img = img.resize((640, 480), Image.Resampling.LANCZOS)
            imgtk = ImageTk.PhotoImage(image=img)

            self.video_label.imgtk = imgtk
            self.video_label.config(image=imgtk)
        
        if self.camera_active:
            self.root.after(33, self._update_camera)  # ~30 FPS

    def _toggle_recognition(self):
        """Active/désactive la reconnaissance faciale."""
        self.recognition_active = not self.recognition_active
        
        if self.recognition_active:
            self.btn_recognition.config(text="Désactiver Reconnaissance")
            self.recognition_status.config(text="🔍 Reconnaissance: Active")
        else:
            self.btn_recognition.config(text="Activer Reconnaissance")
            self.recognition_status.config(text="🔍 Reconnaissance: Inactive")

        if not self.recognition_active:
            self._last_annotated_frame = None
            with self._results_lock:
                self._pending_results = None

        self._sync_status_badges()

    def _recognition_worker(self, frame: cv2.Mat):
        """Effectue la reconnaissance faciale en arrière-plan."""
        try:
            results = face_recognizer.recognize(frame)
            with self._results_lock:
                self._pending_results = (frame, results)
        finally:
            self._recognition_busy = False

    def _apply_recognition_results(self, frame: cv2.Mat, results: List[Dict]) -> cv2.Mat:
        """
        Applique les résultats de reconnaissance sur une frame avec anti-spoofing.
        
        Args:
            frame: Image de la caméra
            
        Returns:
            Image avec les annotations
        """
        for result in results:
            x, y, w, h = result['face_rect']
            
            # Afficher le statut anti-spoofing
            self._update_spoofing_display(result)
            
            # Vérifier si le visage est réel
            if 'is_real' in result and not result['is_real']:
                # 🚨 USURPATION DÉTECTÉE (SPOOFING ATTEMPT - PHOTO/VIDÉO)
                color = (0, 0, 255)  # Bright Red
                
                # Draw VERY thick red rectangle (5 pixels)
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 5)
                
                # Draw LARGE red filled background for alert text
                cv2.rectangle(frame, (x-10, y-85), (x+w+10, y-5), (0, 0, 200), -1)
                
                # Draw ALERT text in BRIGHT WHITE and LARGE FONT
                cv2.putText(frame, "🚨 ALERTE USURPATION 🚨", (x+5, y-65), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 3)
                cv2.putText(frame, "PHOTO / VIDEO DETECTEE", (x+5, y-40), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                cv2.putText(frame, f"ACCES REFUSE - Confiance: {result['spoofing_confidence']:.1%}", 
                           (x+5, y-15), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                
                # Update status with VERY CLEAR message
                self._update_access_status('danger', 
                    f"🚨🚨🚨 USURPATION DETECTABLE! PHOTO/VIDEO DETECTEE - ACCES REFUSE! Confiance: {result['spoofing_confidence']:.1%} 🚨🚨🚨")
                
                # Log the spoofing attempt
                self._record_access(result, None, 'IMPOSTOR', frame)
                continue
            
            user = db_manager.get_user(user_id=result['user_id']) if (result['recognized'] and result['user_id']) else None

            if user:
                # ✅ REGISTERED PERSON (PERSONNE ENREGISTRÉE)
                is_authorized = user.get('is_authorized', False)
                
                if is_authorized:
                    # ✅ AUTHORIZED + REGISTERED (AUTHORIZED)
                    color = (0, 255, 0)  # Green
                    bg_color = (25, 160, 25)  # Dark green for background
                    access_type = 'AUTHORIZED'
                    status_icon = "✅"
                    status_text = "AUTORISÉ"
                    self._update_access_status('success', 
                                              f"✅ Accès AUTORISÉ: {user['full_name']}")
                else:
                    # ⚠️ NOT AUTHORIZED BUT REGISTERED (KNOWN_UNAUTHORIZED)
                    color = (0, 165, 255)  # Orange
                    bg_color = (0, 128, 200)  # Dark orange for background
                    access_type = 'KNOWN_UNAUTHORIZED'
                    status_icon = "⚠️"
                    status_text = "REFUSÉ"
                    self._update_access_status('warning',
                                              f"⚠️ Accès REFUSÉ: {user['full_name']}")
                
                # Enregistrer l'accès
                self._record_access(result, user, access_type, frame)
                
                # Draw thick rectangle with background
                cv2.rectangle(frame, (x-5, y-65), (x+w+5, y-5), bg_color, -1)
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 3)
                
                # Display registered person with full details
                name = user['full_name']
                cv2.putText(frame, f"{status_icon} {status_text} - {name}", 
                           (x+5, y-45), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, f"ID: {user['id']} | Confiance: {result['confidence']:.1f}%",
                           (x+5, y-20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.putText(frame, f"ENREGISTRÉ(E) DANS LE SYSTÈME",
                           (x+5, y-3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            else:
                # ❌ UNKNOWN PERSON (PERSONNE NON ENREGISTRÉE)
                color = (0, 0, 255)  # Red
                bg_color = (0, 0, 200)  # Dark red for background
                
                # Draw thick red rectangle with background
                cv2.rectangle(frame, (x-5, y-65), (x+w+5, y-5), bg_color, -1)
                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 3)
                
                # Display unknown person
                cv2.putText(frame, "❌ INCONNU(E) - NON ENREGISTRÉ(E)", 
                           (x+5, y-45), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, f"Confiance: {result['confidence']:.1f}%",
                           (x+5, y-20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.putText(frame, f"PAS DANS LE SYSTÈME - ACCÈS REFUSÉ",
                           (x+5, y-3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                self._update_access_status('danger', "❓ Personne INCONNUE et NON ENREGISTRÉE détectée")
                self._record_access(result, None, 'UNKNOWN', frame)
        
        return frame

    def _record_access(self, result: Dict, user: Optional[Dict], 
                       access_type: str, frame: cv2.Mat):
        """Enregistre un événement d'accès avec détails complets pour tous les types."""
        # Éviter les enregistrements trop rapprochés
        if not hasattr(self, '_last_record_time'):
            self._last_record_time = {}
        
        user_id = user['id'] if user else None
        key = f"{user_id}_{access_type}"
        current_time = time.time()
        
        if key in self._last_record_time:
            if current_time - self._last_record_time[key] < 10:  # 10 secondes minimum
                return
        
        # Ignorer les faux positifs spoofing extrêmes
        if access_type == 'IMPOSTOR' and result['spoofing_confidence'] < 0.3:
            return
        
        self._last_record_time[key] = current_time
        
        # Sauvegarder la capture
        capture_path = face_recognizer.save_capture(
            frame, result['face_rect'], 
            prefix=access_type.lower()
        )
        
        # Créer le log avec détails complets
        access_result = "GRANTED" if access_type == "AUTHORIZED" else "DENIED"
        
        # Construire les détails en fonction du type d'accès
        if access_type == 'IMPOSTOR':
            # SPECIAL DETAILED LOGGING FOR SPOOFING/USURPATION ATTEMPTS
            details_parts = [
                "🚨 ALERTE USURPATION: Tentative de photo/vidéo détectée",
                f"Confiance Usurpation: {result['spoofing_confidence']:.1%}",
                f"Statut Visage: ❌ USURPATION (Photo/Vidéo/Faux)"
            ]
        else:
            details_parts = [f"Reconnaissance automatique"]
            details_parts.append(f"Confiance Reconnaissance: {result['confidence']:.1f}%")
        
        # Ajouter les détails anti-spoofing
        if 'spoofing_confidence' in result:
            details_parts.append(f"Anti-spoofing: {result['spoofing_confidence']:.1%}")
        
        if 'is_real' in result and access_type != 'IMPOSTOR':
            if result['is_real']:
                details_parts.append("Statut Visage: ✅ RÉEL détecté")
            else:
                details_parts.append("Statut Visage: ❌ USURPATION détectée (Photo/Vidéo)")
        
        # Ajouter les détails spoofing si disponibles
        spoofing_details = result.get('spoofing_details', {})
        if spoofing_details:
            if access_type == 'IMPOSTOR' or not result.get('is_real', True):
                # Pour les usurpations, enregistrer les méthodes qui ont détecté le spoofing
                details_parts.append("Méthodes de Détection Anti-Spoofing:")
                for method, score in spoofing_details.items():
                    if isinstance(score, float):
                        details_parts.append(f"  • {method.upper()}: {score:.1%}")
        
        # Type de personne détectée
        if user:
            person_status = f"ENREGISTRÉ(E) - {user['full_name']} (ID: {user_id})"
            if user.get('is_authorized'):
                person_status += " - AUTORISÉ(E)"
            else:
                person_status += " - NON AUTORISÉ(E)"
        else:
            person_status = "NON ENREGISTRÉ(E) - INCONNU(E)"
        
        details_parts.insert(0, f"Personne: {person_status}")

        log_id = db_manager.add_access_log(
            access_type=access_type,
            access_result=access_result,
            user_id=user_id,
            zone_id=self.current_zone_id,
            confidence_score=result['confidence'],
            capture_path=capture_path,
            details=" | ".join(details_parts)
        )
        
        # Récupérer les données du log pour le tatouage
        log_data = db_manager.get_log(log_id)
        
        # Appliquer le tatouage
        try:
            watermarked_path, watermark_hash = watermark_manager.watermark_log_image(
                log_data, capture_path
            )
            db_manager.update_log_watermark(log_id, watermark_hash, watermarked_path)
        except Exception as e:
            print(f"[WARNING] Erreur de tatouage: {e}")
        
        # Déclencher l'alerte appropriée pour les accès non autorisés et spoofing
        if access_type != 'AUTHORIZED':
            log_data['full_name'] = user['full_name'] if user else 'Inconnu'
            alert_manager.trigger_alert(access_type, log_data, capture_path)
            
            # Créer l'alerte en base avec le niveau approprié
            if access_type == 'IMPOSTOR':
                alert_level = config.ALERT_LEVELS['ALARM']  # ALARM for spoofing
                alert_message = f"🚨🚨🚨 ALERTE USURPATION DETECTÉE 🚨🚨🚨 - Photo/Vidéo tentée - Confiance: {result['spoofing_confidence']:.1%} - ACCES REFUSE"
            elif access_type == 'UNKNOWN':
                alert_level = config.ALERT_LEVELS['WARNING']  # WARNING for unknown
                alert_message = f"⚠️ Personne NON ENREGISTRÉE détectée - Accès refusé"
            else:  # KNOWN_UNAUTHORIZED
                alert_level = config.ALERT_LEVELS['WARNING']  # WARNING for unauthorized
                alert_message = f"⚠️ Accès REFUSÉ: {user['full_name']} - Non autorisé(e)"
            
            db_manager.add_alert(
                log_id=log_id,
                alert_level=alert_level,
                alert_type=access_type,
                message=alert_message
            )
        
        # Rafraîchir les affichages
        self._refresh_recent_logs()

    def _update_access_status(self, status_type: str, message: str):
        """Met à jour l'affichage du statut d'accès."""
        colors = {
            'success': ('🟢', self.theme['success']),
            'warning': ('🟠', self.theme['warning']),
            'danger': ('🔴', self.theme['danger']),
            'info': ('🔵', self.theme['accent'])
        }
        
        icon, color = colors.get(status_type, ('⚪', self.theme['muted']))
        self.status_icon.config(text=icon, foreground=color)
        self.status_text.config(text=message)

    def _update_spoofing_display(self, result: Dict):
        """Met à jour l'affichage anti-spoofing avec des indicateurs TRÈS CLAIRS."""
        if 'is_real' not in result:
            self.spoofing_status.config(text="⏳ Vérification en cours...", foreground=self.theme['muted'])
            self.spoofing_confidence.config(text="", foreground=self.theme['muted'])
            self.spoofing_details.config(text="")
            self.spoofing_meter.config(style='SpoofingIdle.TProgressbar')
            self.spoofing_meter['value'] = 0
            return
        
        is_real = result['is_real']
        confidence = result['spoofing_confidence']
        details = result.get('spoofing_details', {})
        
        if is_real:
            # ✅ REAL FACE DETECTED
            status_text = "✅ VISAGE AUTHENTIQUE - REAL FACE"
            color = self.theme['success']
            meter_style = 'SpoofingOk.TProgressbar'
            meter_value = 100
            detail_prefix = "✅ ANALYSE: Visage réel détecté"
        else:
            # 🚨 SPOOFING DETECTED - PHOTO/VIDEO
            status_text = "🚨🚨🚨 USURPATION DETECTÉE - PHOTO/VIDEO 🚨🚨🚨"
            color = self.theme['danger']
            meter_style = 'SpoofingBad.TProgressbar'
            meter_value = 100
            detail_prefix = "🚨 ALERTE USURPATION: Photo/Vidéo détectée"
        
        self.spoofing_status.config(text=status_text, foreground=color)
        self.spoofing_confidence.config(
            text=f"Confiance Analyse: {confidence:.1%}", 
            foreground=color
        )
        self.spoofing_meter.config(style=meter_style)
        self.spoofing_meter['value'] = meter_value
        
        # Afficher les détails complets de l'analyse anti-spoofing
        if details:
            detail_text = f"{detail_prefix}\n\n📊 Analyse détaillée:\n"
            label_map = {
                'texture': '🏗️ Texture',
                'color': '🎨 Couleur',
                'frequency': '📡 Fréquence',
                'motion': '🎬 Mouvement',
                'glare': '💡 Reflets'
            }
            
            for method, score in details.items():
                if isinstance(score, float):
                    label = label_map.get(method, method.capitalize())
                    # Create visual bar
                    bar_length = int(score * 10)
                    bar = "█" * bar_length + "░" * (10 - bar_length)
                    detail_text += f"  {label}: {bar} {score:.0%}\n"
            
            self.spoofing_details.config(text=detail_text.strip())
        else:
            if not is_real:
                self.spoofing_details.config(text="🚨 USURPATION DETECTÉE - ACCES REFUSE")
            else:
                self.spoofing_details.config(text="Analyse complète")

    # =========================================================================
    # GESTION DES UTILISATEURS
    # =========================================================================

    def _add_user_dialog(self):
        """Ouvre le dialogue d'ajout d'utilisateur."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Ajouter un utilisateur")
        dialog.geometry("400x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Champs du formulaire
        fields = {}
        
        ttk.Label(dialog, text="Nom d'utilisateur:").pack(pady=5)
        fields['username'] = ttk.Entry(dialog, width=40)
        fields['username'].pack()
        
        ttk.Label(dialog, text="Nom complet:").pack(pady=5)
        fields['full_name'] = ttk.Entry(dialog, width=40)
        fields['full_name'].pack()
        
        ttk.Label(dialog, text="Email:").pack(pady=5)
        fields['email'] = ttk.Entry(dialog, width=40)
        fields['email'].pack()
        
        ttk.Label(dialog, text="Téléphone:").pack(pady=5)
        fields['phone'] = ttk.Entry(dialog, width=40)
        fields['phone'].pack()
        
        ttk.Label(dialog, text="Département:").pack(pady=5)
        fields['department'] = ttk.Entry(dialog, width=40)
        fields['department'].pack()
        
        ttk.Label(dialog, text="Rôle:").pack(pady=5)
        fields['role'] = ttk.Combobox(dialog, values=['user', 'admin', 'security'], width=37)
        fields['role'].set('user')
        fields['role'].pack()
        
        # Checkboxes
        fields['is_authorized'] = tk.BooleanVar()
        ttk.Checkbutton(dialog, text="Autorisé à accéder", 
                       variable=fields['is_authorized']).pack(pady=5)
        
        fields['consent_given'] = tk.BooleanVar()
        ttk.Checkbutton(dialog, text="Consentement RGPD donné", 
                       variable=fields['consent_given']).pack(pady=5)
        
        def save_user():
            try:
                user_id = db_manager.add_user(
                    username=fields['username'].get(),
                    full_name=fields['full_name'].get(),
                    email=fields['email'].get(),
                    phone=fields['phone'].get(),
                    department=fields['department'].get(),
                    role=fields['role'].get(),
                    is_authorized=fields['is_authorized'].get(),
                    consent_given=fields['consent_given'].get()
                )
                messagebox.showinfo("Succès", f"Utilisateur créé avec l'ID {user_id}")
                self._refresh_users_list()
                self._load_users_info()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Erreur", str(e))
        
        ttk.Button(dialog, text="Enregistrer", command=save_user).pack(pady=20)

    def _edit_user(self):
        """Modifie l'utilisateur sélectionné."""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Veuillez sélectionner un utilisateur")
            return
        
        user_id = int(self.users_tree.item(selection[0])['values'][0])
        user = db_manager.get_user(user_id=user_id)
        
        if not user:
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Modifier: {user['full_name']}")
        dialog.geometry("400x500")
        dialog.transient(self.root)
        dialog.grab_set()
        
        fields = {}
        
        ttk.Label(dialog, text="Nom complet:").pack(pady=5)
        fields['full_name'] = ttk.Entry(dialog, width=40)
        fields['full_name'].insert(0, user['full_name'])
        fields['full_name'].pack()
        
        ttk.Label(dialog, text="Email:").pack(pady=5)
        fields['email'] = ttk.Entry(dialog, width=40)
        fields['email'].insert(0, user['email'] or '')
        fields['email'].pack()
        
        ttk.Label(dialog, text="Département:").pack(pady=5)
        fields['department'] = ttk.Entry(dialog, width=40)
        fields['department'].insert(0, user['department'] or '')
        fields['department'].pack()
        
        ttk.Label(dialog, text="Rôle:").pack(pady=5)
        fields['role'] = ttk.Combobox(dialog, values=['user', 'admin', 'security'], width=37)
        fields['role'].set(user['role'])
        fields['role'].pack()
        
        fields['is_authorized'] = tk.BooleanVar(value=bool(user['is_authorized']))
        ttk.Checkbutton(dialog, text="Autorisé à accéder", 
                       variable=fields['is_authorized']).pack(pady=5)
        
        fields['is_active'] = tk.BooleanVar(value=bool(user['is_active']))
        ttk.Checkbutton(dialog, text="Compte actif", 
                       variable=fields['is_active']).pack(pady=5)
        
        def save_changes():
            try:
                db_manager.update_user(
                    user_id,
                    full_name=fields['full_name'].get(),
                    email=fields['email'].get(),
                    department=fields['department'].get(),
                    role=fields['role'].get(),
                    is_authorized=fields['is_authorized'].get(),
                    is_active=fields['is_active'].get()
                )
                messagebox.showinfo("Succès", "Utilisateur mis à jour")
                self._refresh_users_list()
                self._load_users_info()
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Erreur", str(e))
        
        ttk.Button(dialog, text="Enregistrer", command=save_changes).pack(pady=20)

    def _delete_user(self):
        """Supprime l'utilisateur sélectionné."""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Veuillez sélectionner un utilisateur")
            return
        
        user_id = int(self.users_tree.item(selection[0])['values'][0])
        
        if messagebox.askyesno("Confirmation", 
                               "Voulez-vous désactiver cet utilisateur?\n"
                               "(Les données seront conservées conformément au RGPD)"):
            db_manager.delete_user(user_id, hard_delete=False)
            self._refresh_users_list()
            messagebox.showinfo("Succès", "Utilisateur désactivé")

    def _register_face(self):
        """Enregistre le visage d'un utilisateur."""
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Veuillez sélectionner un utilisateur")
            return
        
        user_id = int(self.users_tree.item(selection[0])['values'][0])
        user = db_manager.get_user(user_id=user_id)
        
        if not user:
            return
        
        if not messagebox.askyesno("Confirmation",
                                   f"Enregistrer le visage de {user['full_name']}?\n"
                                   "La caméra va capturer plusieurs images."):
            return
        
        # S'assurer que la caméra est active
        if not self.camera_active:
            self._start_camera()
            time.sleep(1)
        
        # Fenêtre de progression
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Capture en cours...")
        progress_window.geometry("400x150")
        progress_window.transient(self.root)
        
        ttk.Label(progress_window, text=f"Capture du visage de {user['full_name']}",
             font=self.fonts['header']).pack(pady=10)
        
        progress_bar = ttk.Progressbar(progress_window, length=300, mode='determinate')
        progress_bar.pack(pady=10)
        
        progress_label = ttk.Label(progress_window, text="Placez votre visage devant la caméra...")
        progress_label.pack(pady=5)
        
        def capture_callback(progress, frame):
            progress_bar['value'] = progress * 100
            progress_label.config(text=f"Capture: {int(progress * 100)}%")
            progress_window.update()
        
        # Effectuer la capture dans un thread
        def do_capture():
            try:
                faces = face_recognizer.capture_training_images(
                    self.camera,
                    num_images=config.FACE_RECOGNITION['training_images_per_user'],
                    callback=capture_callback
                )
                
                if len(faces) >= 5:
                    # Enregistrer les encodages
                    face_encoding = face_recognizer.save_face_encoding_for_db(faces)
                    db_manager.update_face_encoding(user_id, face_encoding)
                    
                    # Enregistrer dans le recognizer
                    face_recognizer.register_face(user_id, faces)
                    
                    progress_window.destroy()
                    messagebox.showinfo("Succès", 
                                       f"Visage de {user['full_name']} enregistré avec succès!")
                    self._refresh_users_list()
                else:
                    progress_window.destroy()
                    messagebox.showerror("Erreur", 
                                        "Pas assez d'images capturées. Réessayez.")
            except Exception as e:
                progress_window.destroy()
                messagebox.showerror("Erreur", str(e))
        
        threading.Thread(target=do_capture, daemon=True).start()

    def _refresh_users_list(self):
        """Rafraîchit la liste des utilisateurs."""
        for item in self.users_tree.get_children():
            self.users_tree.delete(item)
        
        users = db_manager.get_all_users(active_only=False)
        
        for user in users:
            has_face = "✓" if user['face_encoding'] else "✗"
            authorized = "✓" if user['is_authorized'] else "✗"
            
            self.users_tree.insert('', tk.END, values=(
                user['id'],
                user['full_name'],
                user['email'] or '-',
                user['department'] or '-',
                user['role'],
                authorized,
                has_face
            ))

    def _manage_users_dialog(self):
        """Ouvre le dialogue de gestion des utilisateurs."""
        self.notebook.select(self.users_frame)

    def _train_model(self):
        """Entraîne le modèle de reconnaissance faciale."""
        users = db_manager.get_authorized_users()
        
        if not users:
            messagebox.showwarning("Attention", "Aucun utilisateur autorisé avec visage enregistré")
            return
        
        try:
            success = face_recognizer.train_from_database(users)
            if success:
                messagebox.showinfo("Succès", 
                                   f"Modèle entraîné avec {len(users)} utilisateurs")
            else:
                messagebox.showwarning("Attention", 
                                      "Entraînement terminé avec des avertissements")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur d'entraînement: {e}")

    # =========================================================================
    # GESTION DES LOGS
    # =========================================================================

    def _refresh_logs_list(self, access_type_filter: str = None):
        """Rafraîchit la liste des logs avec filtrage optionnel."""
        for item in self.logs_tree.get_children():
            self.logs_tree.delete(item)
        
        logs = db_manager.get_access_logs(limit=200)
        
        for log in logs:
            # Apply filter if specified
            if access_type_filter and log['access_type'] != access_type_filter:
                continue
            
            watermarked = "✓" if log['is_watermarked'] else "✗"
            user_name = log['full_name'] or log['username'] or '-'
            
            # Add status indicator
            access_type = log['access_type']
            if access_type == 'AUTHORIZED':
                status_icon = "✅"
            elif access_type == 'IMPOSTOR':
                status_icon = "🚨"
            elif access_type == 'UNKNOWN':
                status_icon = "❓"
            else:  # KNOWN_UNAUTHORIZED
                status_icon = "⚠️"
            
            # Convert confidence_score to float safely
            confidence = log['confidence_score']
            try:
                if isinstance(confidence, bytes):
                    confidence = float(confidence.decode('utf-8'))
                elif confidence is not None:
                    confidence = float(confidence)
                confidence_str = f"{confidence:.1f}%" if confidence else '-'
            except (ValueError, UnicodeDecodeError):
                confidence_str = '-'
            
            self.logs_tree.insert('', tk.END, values=(
                log['id'],
                log['timestamp'][:19],
                user_name,
                f"{status_icon} {log['access_type']}",
                log['access_result'],
                confidence_str,
                watermarked
            ))

    def _refresh_recent_logs(self):
        """Rafraîchit la liste des logs récents dans l'onglet accès."""
        self.recent_logs_list.delete(0, tk.END)
        
        logs = db_manager.get_access_logs(limit=10)
        
        for log in logs:
            user_name = log['full_name'] or 'Inconnu'
            time_str = log['timestamp'][11:19] if log['timestamp'] else ''
            access_type = log['access_type']
            
            # Create status icon based on access type
            if access_type == 'AUTHORIZED':
                status_icon = "✅"  # Green - Authorized
                status_text = "AUTORISÉ"
            elif access_type == 'IMPOSTOR':
                status_icon = "🚨"  # Red alert - Spoofing
                status_text = "USURPATION"
            elif access_type == 'UNKNOWN':
                status_icon = "❓"  # Unknown
                status_text = "NON ENREGISTRÉ"
            else:  # KNOWN_UNAUTHORIZED
                status_icon = "⚠️"  # Orange warning
                status_text = "REFUSÉ"
            
            # Format: [TIME] [ICON] [TYPE] | [PERSON] | [CONFIDENCE]
            confidence = log['confidence_score']
            try:
                if isinstance(confidence, bytes):
                    confidence = float(confidence.decode('utf-8'))
                elif confidence is not None:
                    confidence = float(confidence)
                conf_str = f"{confidence:.1f}%" if confidence else '-'
            except (ValueError, UnicodeDecodeError):
                conf_str = '-'
            
            log_entry = f"{time_str} {status_icon} {status_text:12} | {user_name:20} | Conf: {conf_str}"
            self.recent_logs_list.insert(tk.END, log_entry)

    def _search_logs(self):
        """Recherche dans les logs avec les filtres."""
        access_type = self.filter_type.get()
        
        # Extract access type code from description if present
        if access_type and ' - ' in access_type:
            access_type = access_type.split(' - ')[0]
        
        if access_type == 'Tous':
            access_type = None
        
        # Re-filtrer
        self._refresh_logs_list(access_type)

    def _reset_log_filters(self):
        """Réinitialise les filtres de recherche."""
        self.filter_type.set('Tous')
        self._refresh_logs_list()

    def _show_log_context_menu(self, event):
        """Affiche le menu contextuel des logs."""
        item = self.logs_tree.identify_row(event.y)
        if item:
            self.logs_tree.selection_set(item)
            self.log_context_menu.post(event.x_root, event.y_root)

    def _view_log_details(self):
        """Affiche les détails d'un log."""
        selection = self.logs_tree.selection()
        if not selection:
            return
        
        log_id = int(self.logs_tree.item(selection[0])['values'][0])
        log = db_manager.get_log(log_id)
        
        if not log:
            return
        
        details = f"""
        ID: {log['id']}
        Date/Heure: {log['timestamp']}
        Type d'accès: {log['access_type']}
        Résultat: {log['access_result']}
        Utilisateur: {log['full_name'] or 'N/A'} (ID: {log['user_id'] or 'N/A'})
        Zone: {log['zone_name'] or 'N/A'}
        Confiance: {log['confidence_score'] or 'N/A'}%
        Tatoué: {'Oui' if log['is_watermarked'] else 'Non'}
        Hash: {log['watermark_hash'] or 'N/A'}
        Détails: {log['details'] or 'N/A'}
        """
        
        messagebox.showinfo("Détails du log", details)

    def _verify_log_watermark(self):
        """Vérifie le tatouage d'un log sélectionné."""
        selection = self.logs_tree.selection()
        if not selection:
            return
        
        log_id = int(self.logs_tree.item(selection[0])['values'][0])
        log = db_manager.get_log(log_id)
        
        if not log or not log['watermarked_image_path']:
            messagebox.showwarning("Attention", "Ce log n'a pas d'image tatouée")
            return
        
        result = watermark_manager.verify_log_integrity(log['watermarked_image_path'])
        
        if result['is_valid']:
            messagebox.showinfo("Vérification", 
                              f"✓ Tatouage VALIDE\n\n"
                              f"Intégrité vérifiée!\n\n"
                              f"Données extraites:\n{result['data']}")
        else:
            messagebox.showwarning("Vérification",
                                  f"✗ Tatouage INVALIDE\n\n"
                                  f"Message: {result['message']}")

    def _view_capture(self):
        """Affiche la capture d'un log."""
        selection = self.logs_tree.selection()
        if not selection:
            return
        
        log_id = int(self.logs_tree.item(selection[0])['values'][0])
        log = db_manager.get_log(log_id)
        
        if not log or not log['capture_path']:
            messagebox.showwarning("Attention", "Pas de capture disponible")
            return
        
        if not os.path.exists(log['capture_path']):
            messagebox.showwarning("Attention", "Fichier de capture introuvable")
            return
        
        # Ouvrir dans une nouvelle fenêtre
        img_window = tk.Toplevel(self.root)
        img_window.title(f"Capture - Log #{log_id}")
        
        img = Image.open(log['capture_path'])
        img.thumbnail((800, 600))
        imgtk = ImageTk.PhotoImage(img)
        
        label = ttk.Label(img_window, image=imgtk)
        label.image = imgtk
        label.pack()

    # =========================================================================
    # GESTION DES ALERTES
    # =========================================================================

    def _refresh_alerts(self):
        """Rafraîchit la liste des alertes."""
        for item in self.alerts_tree.get_children():
            self.alerts_tree.delete(item)
        
        alerts = db_manager.get_pending_alerts()
        
        for alert in alerts:
            level_names = {0: 'INFO', 1: 'WARNING', 2: 'CRITICAL', 3: 'ALARM'}
            level_name = level_names.get(alert['alert_level'], 'UNKNOWN')
            
            tag = 'info'
            if alert['alert_level'] >= 3:
                tag = 'critical'
            elif alert['alert_level'] >= 1:
                tag = 'warning'
            
            self.alerts_tree.insert('', tk.END, values=(
                alert['id'],
                alert['created_at'][:19],
                level_name,
                alert['alert_type'],
                alert['message'][:50] if alert['message'] else '-',
                alert['user_name'] or 'Inconnu'
            ), tags=(tag,))

    def _acknowledge_selected_alert(self):
        """Acquitte l'alerte sélectionnée."""
        selection = self.alerts_tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Veuillez sélectionner une alerte")
            return
        
        alert_id = int(self.alerts_tree.item(selection[0])['values'][0])
        
        # Pour simplifier, on utilise l'ID 1 comme admin (à améliorer avec système d'authentification)
        db_manager.acknowledge_alert(alert_id, user_id=1)
        messagebox.showinfo("Succès", "Alerte acquittée")
        self._refresh_alerts()

    # =========================================================================
    # STATISTIQUES
    # =========================================================================

    def _refresh_stats(self):
        """Rafraîchit les statistiques."""
        stats = db_manager.get_statistics(days=30)
        
        self.stat_cards['total_access'].config(text=str(stats.get('total_access', 0)))
        self.stat_cards['authorized'].config(
            text=str(stats.get('by_type', {}).get('AUTHORIZED', 0)))
        denied = (stats.get('by_type', {}).get('KNOWN_UNAUTHORIZED', 0) +
                  stats.get('by_type', {}).get('IMPOSTOR', 0))
        self.stat_cards['denied'].config(text=str(denied))
        self.stat_cards['alerts'].config(text=str(stats.get('pending_alerts', 0)))
        self.stat_cards['users'].config(text=str(stats.get('active_users', 0)))
        
        # Détails
        self.stats_text.delete(1.0, tk.END)
        details = f"""
STATISTIQUES DES 30 DERNIERS JOURS
==================================

Total des accès: {stats.get('total_access', 0)}

Répartition par type:
---------------------
"""
        for access_type, count in stats.get('by_type', {}).items():
            details += f"  • {access_type}: {count}\n"
        
        details += f"""
Alertes en attente: {stats.get('pending_alerts', 0)}
Utilisateurs actifs: {stats.get('active_users', 0)}
Utilisateurs autorisés: {stats.get('authorized_users', 0)}

Dernière mise à jour: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        self.stats_text.insert(tk.END, details)

    # =========================================================================
    # UTILITAIRES
    # =========================================================================

    def _refresh_zones(self):
        """Rafraîchit la liste des zones."""
        zones = db_manager.get_zones()
        self.zone_combo['values'] = [f"{z['id']} - {z['name']}" for z in zones]
        if zones:
            self.zone_combo.current(0)
            self.current_zone_id = zones[0]['id']

    def _export_logs(self):
        """Exporte les logs vers un fichier."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("CSV", "*.csv")],
            title="Exporter les logs"
        )
        
        if not filepath:
            return
        
        try:
            import json
            logs = db_manager.get_access_logs(limit=10000)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(logs, f, ensure_ascii=False, indent=2)
            
            messagebox.showinfo("Succès", f"Logs exportés vers {filepath}")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur d'export: {e}")

    def _import_faces(self):
        """Importe des visages depuis un dossier."""
        folder = filedialog.askdirectory(title="Sélectionner le dossier des visages")
        if not folder:
            return
        
        messagebox.showinfo("Info", 
                           "Fonctionnalité à implémenter: import de visages depuis dossier")

    def _verify_watermark_dialog(self):
        """Ouvre le dialogue de vérification de tatouage."""
        filepath = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")],
            title="Sélectionner une image tatouée"
        )
        
        if not filepath:
            return
        
        result = watermark_manager.verify_log_integrity(filepath)
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Résultat de vérification")
        dialog.geometry("500x400")
        
        if result['is_valid']:
            ttk.Label(dialog, text="✓ TATOUAGE VALIDE", style='Success.TLabel',
                     font=self.fonts['big']).pack(pady=20)
        else:
            ttk.Label(dialog, text="✗ TATOUAGE INVALIDE", style='Danger.TLabel',
                     font=self.fonts['big']).pack(pady=20)
        
        ttk.Label(dialog, text=f"Message: {result['message']}").pack(pady=5)
        ttk.Label(dialog, text=f"Date de vérification: {result['verification_time']}").pack(pady=5)
        
        if result['data']:
            ttk.Label(dialog, text="Données extraites:").pack(pady=10)
            text = tk.Text(dialog, height=10, width=50)
            text.pack(pady=5)
            text.insert(tk.END, str(result['data']))
            text.config(state=tk.DISABLED)

    def _test_robustness_dialog(self):
        """Teste la robustesse du tatouage."""
        filepath = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp")],
            title="Sélectionner une image tatouée"
        )
        
        if not filepath:
            return
        
        results = watermark_manager.test_robustness(filepath)
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Test de robustesse")
        dialog.geometry("400x350")
        
        ttk.Label(dialog, text="Résultats du test de robustesse", 
             font=self.fonts['header']).pack(pady=10)
        
        for test_name, passed in results.items():
            status = "✓ Réussi" if passed else "✗ Échoué"
            color = 'green' if passed else 'red'
            label = ttk.Label(dialog, text=f"{test_name}: {status}")
            label.pack(anchor=tk.W, padx=20, pady=2)

    def _show_about(self):
        """Affiche la boîte de dialogue À propos."""
        messagebox.showinfo("À propos",
                           "Système de Contrôle d'Accès Biométrique\n\n"
                           "Version 1.0\n\n"
                           "Fonctionnalités:\n"
                           "• Reconnaissance faciale temps réel\n"
                           "• Tatouage numérique des logs (LSB/DCT)\n"
                           "• Gestion des utilisateurs\n"
                           "• Alertes et notifications\n"
                           "• Conformité RGPD\n\n"
                           "© 2026")

    def _show_documentation(self):
        """Affiche la documentation."""
        doc_window = tk.Toplevel(self.root)
        doc_window.title("Documentation")
        doc_window.geometry("600x500")
        
        text = tk.Text(doc_window, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        
        documentation = """
DOCUMENTATION DU SYSTÈME DE CONTRÔLE D'ACCÈS BIOMÉTRIQUE
=========================================================

1. DÉMARRAGE
-------------
- Cliquez sur "Démarrer Caméra" pour activer la webcam
- Cliquez sur "Activer Reconnaissance" pour démarrer la détection

2. ENREGISTREMENT D'UN UTILISATEUR
-----------------------------------
- Onglet "Utilisateurs" > "Ajouter"
- Remplissez les informations
- Sélectionnez l'utilisateur et cliquez sur "Enregistrer visage"
- Placez-vous devant la caméra pour la capture

3. TATOUAGE NUMÉRIQUE
----------------------
- Chaque accès génère un log tatoué numériquement
- Menu "Tatouage" > "Vérifier un log" pour contrôler l'intégrité
- Menu "Tatouage" > "Test de robustesse" pour tester la résistance

4. TYPES D'ACCÈS
-----------------
- AUTHORIZED: Utilisateur reconnu et autorisé
- KNOWN_UNAUTHORIZED: Utilisateur reconnu mais non autorisé
- IMPOSTOR: Personne non reconnue (alerte critique)

5. ALERTES
-----------
- Les alertes sont générées automatiquement
- Onglet "Alertes" pour voir et acquitter les alertes en attente
- Notifications email configurables dans config.py

6. CONFORMITÉ RGPD
-------------------
- Les données sont automatiquement anonymisées après 30 jours
- Les logs sont supprimés après 90 jours
- Export des données utilisateur disponible
"""
        text.insert(tk.END, documentation)
        text.config(state=tk.DISABLED)

    def _on_closing(self):
        """Gère la fermeture de l'application."""
        if messagebox.askokcancel("Quitter", "Voulez-vous vraiment quitter?"):
            self._stop_camera()
            notification_manager.stop_worker()
            self.root.destroy()


def main():
    """Point d'entrée principal de l'application."""
    root = tk.Tk()
    app = AccessControlApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
