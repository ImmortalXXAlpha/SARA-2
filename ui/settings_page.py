from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QCheckBox, QPushButton,
    QTabWidget, QHBoxLayout, QComboBox, QLineEdit, QTextEdit,
    QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal


class SettingsPage(QWidget):
    theme_changed = Signal(str)  # Signal to notify theme change
    
    def __init__(self):
        super().__init__()
        self.current_theme = "dark"  # Track current theme
        
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(25)

        title = QLabel("⚙️ Settings")
        title.setObjectName("title")
        subtitle = QLabel("Customize your SARA preferences and behavior")
        subtitle.setObjectName("subtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Create tabs
        tabs = QTabWidget()
        # Don't override stylesheet here - let parent handle it

        # Add tabs
        tabs.addTab(self.create_general_tab(), "⚙️ General")
        tabs.addTab(self.create_ai_models_tab(), "🧠 AI Models")
        tabs.addTab(self.create_scripts_tab(), "📜 Scripts")

        layout.addWidget(tabs)
        self.setLayout(layout)

    # ==================== GENERAL TAB ====================
    def create_general_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # System Preferences Section
        sys_pref_label = QLabel("System Preferences")
        sys_pref_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        
        sys_pref_subtitle = QLabel("Configure automatic scans and system behavior")
        sys_pref_subtitle.setStyleSheet("font-size: 13px; margin-bottom: 10px;")

        layout.addWidget(sys_pref_label)
        layout.addWidget(sys_pref_subtitle)

        # Settings card - removed hardcoded background
        settings_card = QFrame()
        settings_card.setStyleSheet("""
            QFrame {
                border-radius: 12px;
                border: 1px solid #2b3548;
                padding: 10px;
            }
        """)
        inner = QVBoxLayout(settings_card)
        inner.setContentsMargins(20, 20, 20, 20)
        inner.setSpacing(15)

        # Theme toggle
        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme Mode")
        theme_label.setStyleSheet("font-size: 14px;")
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark Mode", "Light Mode"])
        self.theme_combo.setCurrentText("Dark Mode")
        self.theme_combo.setStyleSheet("""
            QComboBox {
                min-width: 150px;
            }
        """)
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        
        theme_layout.addWidget(theme_label)
        theme_layout.addStretch()
        theme_layout.addWidget(self.theme_combo)

        # Other checkboxes
        self.notif_check = QCheckBox("Enable Notifications")
        self.notif_check.setChecked(True)
        
        self.updates_check = QCheckBox("Automatically Check for Updates")
        self.updates_check.setChecked(True)
        
        self.auto_scan_check = QCheckBox("Run Daily System Scans")
        self.auto_scan_check.setChecked(True)

        # Scan schedule
        scan_layout = QHBoxLayout()
        scan_label = QLabel("Scan Schedule")
        scan_label.setStyleSheet("font-size: 14px;")
        
        scan_combo = QComboBox()
        scan_combo.addItems(["Daily at 2:00 AM", "Weekly on Sunday", "Manual only"])

        scan_layout.addWidget(scan_label)
        scan_layout.addStretch()
        scan_layout.addWidget(scan_combo)

        # Save button
        save_btn = QPushButton("💾 Save Settings")
        save_btn.setStyleSheet("""
            QPushButton {
                background: #6e8bff;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
            }
            QPushButton:hover { 
                background: #869eff; 
            }
        """)
        save_btn.clicked.connect(self.save_general_settings)

        inner.addLayout(theme_layout)
        inner.addWidget(self.notif_check)
        inner.addWidget(self.updates_check)
        inner.addWidget(self.auto_scan_check)
        inner.addLayout(scan_layout)
        inner.addStretch()
        inner.addWidget(save_btn)

        layout.addWidget(settings_card)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    # ==================== AI MODELS TAB ====================
    def create_ai_models_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Title
        ai_title = QLabel("AI Model Preferences")
        ai_title.setStyleSheet("font-size: 18px; font-weight: 600;")
        
        ai_subtitle = QLabel("Choose and configure AI models for different tasks")
        ai_subtitle.setStyleSheet("font-size: 13px; margin-bottom: 10px;")

        layout.addWidget(ai_title)
        layout.addWidget(ai_subtitle)

        # Model selector card - removed hardcoded background
        model_card = QFrame()
        model_card.setStyleSheet("""
            QFrame {
                border-radius: 12px;
                border: 1px solid #2b3548;
                padding: 10px;
            }
        """)
        model_layout = QVBoxLayout(model_card)
        model_layout.setContentsMargins(20, 20, 20, 20)
        model_layout.setSpacing(15)

        # Primary model selection
        primary_layout = QHBoxLayout()
        primary_label = QLabel("Primary AI Model")
        primary_label.setStyleSheet("font-size: 14px;")
        
        self.model_combo = QComboBox()
        self.model_combo.addItems(["Mistral 7B", "WizardLM 13B"])
        self.model_combo.setStyleSheet("""
            QComboBox {
                min-width: 200px;
            }
        """)
        self.model_combo.currentTextChanged.connect(self.update_model_info)
        
        primary_layout.addWidget(primary_label)
        primary_layout.addStretch()
        primary_layout.addWidget(self.model_combo)

        model_layout.addLayout(primary_layout)

        # Model info display - removed hardcoded background
        self.model_info_frame = QFrame()
        self.model_info_frame.setStyleSheet("""
            QFrame {
                border: 1px solid #2b3548;
                border-radius: 8px;
                padding: 5px;
            }
        """)
        info_layout = QVBoxLayout(self.model_info_frame)
        info_layout.setContentsMargins(15, 15, 15, 15)

        self.model_info_label = QLabel()
        self.model_info_label.setStyleSheet("font-size: 13px; line-height: 1.6;")
        self.model_info_label.setWordWrap(True)
        info_layout.addWidget(self.model_info_label)

        model_layout.addWidget(self.model_info_frame)

        # Update initial model info
        self.update_model_info("Mistral 7B")

        layout.addWidget(model_card)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    # ==================== SCRIPTS TAB ====================
    def create_scripts_tab(self):
        widget = QWidget()
        
        # Create scroll area for scripts
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Title
        scripts_title = QLabel("Script Library Management")
        scripts_title.setStyleSheet("font-size: 18px; font-weight: 600;")
        
        scripts_subtitle = QLabel("Manage custom scripts for specialized system operations")
        scripts_subtitle.setStyleSheet("font-size: 13px; margin-bottom: 10px;")

        layout.addWidget(scripts_title)
        layout.addWidget(scripts_subtitle)

        # Add script form - removed hardcoded background
        add_card = QFrame()
        add_card.setStyleSheet("""
            QFrame {
                border-radius: 12px;
                border: 1px solid #2b3548;
                padding: 10px;
            }
        """)
        add_layout = QVBoxLayout(add_card)
        add_layout.setContentsMargins(20, 20, 20, 20)
        add_layout.setSpacing(12)

        # Script name input
        name_label = QLabel("Script Name")
        name_label.setStyleSheet("font-size: 13px;")
        
        self.script_name_input = QLineEdit()
        self.script_name_input.setPlaceholderText("Enter script name...")

        # Script description input
        desc_label = QLabel("Description")
        desc_label.setStyleSheet("font-size: 13px;")
        
        self.script_desc_input = QTextEdit()
        self.script_desc_input.setPlaceholderText("Enter script description...")
        self.script_desc_input.setMaximumHeight(80)

        # Add button
        add_btn = QPushButton("+ Add Script")
        add_btn.setStyleSheet("""
            QPushButton {
                background: #6e8bff;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 600;
            }
            QPushButton:hover { 
                background: #869eff; 
            }
        """)
        add_btn.clicked.connect(self.add_script)

        add_layout.addWidget(name_label)
        add_layout.addWidget(self.script_name_input)
        add_layout.addWidget(desc_label)
        add_layout.addWidget(self.script_desc_input)
        add_layout.addWidget(add_btn)

        layout.addWidget(add_card)

        # Example scripts
        scripts_data = [
            ("Advanced Registry Cleaner", "Maintenance", 
             "Comprehensive registry cleanup and optimization", "2025-09-23"),
            ("Network Diagnostics", "Network", 
             "Diagnose and fix network connectivity issues", "2025-09-22"),
            ("GPU Performance Test", "Hardware", 
             "Test graphics card performance and stability", "2025-09-21"),
        ]

        for name, category, desc, last_used in scripts_data:
            script_card = self.create_script_card(name, category, desc, last_used)
            layout.addWidget(script_card)

        layout.addStretch()

        scroll.setWidget(scroll_content)
        
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
        
        return widget

    def create_script_card(self, name, category, description, last_used):
        card = QFrame()
        # Removed hardcoded background
        card.setStyleSheet("""
            QFrame {
                border-radius: 12px;
                border: 1px solid #2b3548;
                padding: 10px;
            }
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 15, 20, 15)
        layout.setSpacing(8)

        # Header with name and category
        header_layout = QHBoxLayout()
        
        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 15px; font-weight: 600;")
        
        category_badge = QLabel(category)
        category_badge.setStyleSheet("""
            background: #2b3548;
            color: #9eb3ff;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 600;
        """)
        
        header_layout.addWidget(name_label)
        header_layout.addWidget(category_badge)
        header_layout.addStretch()

        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("font-size: 13px;")
        desc_label.setWordWrap(True)

        # Last used
        last_used_label = QLabel(f"Last used: {last_used}")
        last_used_label.setStyleSheet("font-size: 12px; font-style: italic; opacity: 0.7;")

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        edit_btn = QPushButton("✏️ Edit")
        edit_btn.setStyleSheet("""
            QPushButton {
                background: #4e6baf;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #5a77c4; }
        """)
        
        delete_btn = QPushButton("🗑️ Delete")
        delete_btn.setStyleSheet("""
            QPushButton {
                background: #af4e4e;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #c45a5a; }
        """)
        
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)

        layout.addLayout(header_layout)
        layout.addWidget(desc_label)
        layout.addWidget(last_used_label)
        layout.addLayout(btn_layout)

        return card

    # ==================== EVENT HANDLERS ====================
    def on_theme_changed(self, theme_text):
        """Handle theme change"""
        if theme_text == "Dark Mode":
            self.current_theme = "dark"
        else:
            self.current_theme = "light"
        
        self.theme_changed.emit(self.current_theme)
        print(f"Theme changed to: {self.current_theme}")

    def save_general_settings(self):
        """Save general settings"""
        print("Settings saved!")
        print(f"Theme: {self.current_theme}")
        print(f"Notifications: {self.notif_check.isChecked()}")
        print(f"Auto Updates: {self.updates_check.isChecked()}")
        print(f"Auto Scan: {self.auto_scan_check.isChecked()}")

    def update_model_info(self, model_name):
        """Update the model information display"""
        if model_name == "Mistral 7B":
            info_text = """<b>Mistral 7B</b> — Fast & Efficient
<br><br>
<b>Response Speed:</b> Fast<br>
<b>Accuracy:</b> High<br>
<b>Resource Usage:</b> Low<br>
<br>
Optimized for quick responses and efficient system resource usage. 
Ideal for general system maintenance tasks and quick diagnostics."""
        else:  # WizardLM 13B
            info_text = """<b>WizardLM 13B</b> — Advanced Reasoning
<br><br>
<b>Response Speed:</b> Moderate<br>
<b>Accuracy:</b> Very High<br>
<b>Resource Usage:</b> Medium<br>
<br>
Advanced reasoning capabilities for complex system analysis. 
Best for in-depth diagnostics and detailed troubleshooting."""
        
        self.model_info_label.setText(info_text)

    def add_script(self):
        """Handle adding a new script"""
        name = self.script_name_input.text().strip()
        desc = self.script_desc_input.toPlainText().strip()
        
        if not name or not desc:
            print("Please fill in both script name and description")
            return
        
        print(f"Adding script: {name}")
        print(f"Description: {desc}")
        
        # Clear inputs
        self.script_name_input.clear()
        self.script_desc_input.clear()