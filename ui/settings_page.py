# ui/settings_page.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QCheckBox, QPushButton,
    QTabWidget, QHBoxLayout, QComboBox, QLineEdit, QTextEdit,
    QScrollArea, QSizePolicy, QSlider, QFormLayout, QSpinBox
)
from PySide6.QtCore import Qt, Signal
import json
import os

class SettingsPage(QWidget):
    theme_changed = Signal(str)  # Signal to notify theme change
    ai_settings_changed = Signal(dict)  # Emit advanced AI settings when saved

    def __init__(self, ai=None):
        super().__init__()
        self.ai = ai  # ADDED: Accept shared NovaAI instance
        self.current_theme = "dark"
        self.settings_path = os.path.join(os.path.expanduser("~"), ".sara_settings.json")
        self.settings = self.load_settings()

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

        # Add tabs
        tabs.addTab(self.create_general_tab(), "⚙️ General")
        tabs.addTab(self.create_ai_models_tab(), "🧠 AI Models")
        tabs.addTab(self.create_scripts_tab(), "📜 Scripts")

        layout.addWidget(tabs)
        self.setLayout(layout)

    def load_settings(self):
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # default fallback
            return {
                "default_model": "phi3-mini",
                "force_cpu": False,
                "vram_limit_gb": None,
                "idle_unload_seconds": 600,
                "max_tokens": 256,
                "temperature": 0.7,
                "top_p": 0.9,
                "system_prompt": ""
            }

    def save_settings_file(self, d):
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(d, f, indent=2)
        except Exception as e:
            print("Failed to save settings:", e)

    # ==================== GENERAL TAB ====================
    def create_general_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        sys_pref_label = QLabel("System Preferences")
        sys_pref_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        sys_pref_subtitle = QLabel("Configure automatic scans and system behavior")
        sys_pref_subtitle.setStyleSheet("font-size: 13px; margin-bottom: 10px;")

        layout.addWidget(sys_pref_label)
        layout.addWidget(sys_pref_subtitle)

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

        theme_layout = QHBoxLayout()
        theme_label = QLabel("Theme Mode")
        theme_label.setStyleSheet("font-size: 14px;")
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark Mode", "Light Mode"])
        self.theme_combo.setCurrentText("Dark Mode" if self.current_theme == "dark" else "Light Mode")
        self.theme_combo.currentTextChanged.connect(self.on_theme_changed)
        theme_layout.addWidget(theme_label)
        theme_layout.addStretch()
        theme_layout.addWidget(self.theme_combo)

        self.notif_check = QCheckBox("Enable Notifications")
        self.notif_check.setChecked(self.settings.get("notifications", True))
        self.updates_check = QCheckBox("Automatically Check for Updates")
        self.updates_check.setChecked(self.settings.get("auto_updates", True))
        self.auto_scan_check = QCheckBox("Run Daily System Scans")
        self.auto_scan_check.setChecked(self.settings.get("auto_scan", True))

        scan_layout = QHBoxLayout()
        scan_label = QLabel("Scan Schedule")
        scan_combo = QComboBox()
        scan_combo.addItems(["Daily at 2:00 AM", "Weekly on Sunday", "Manual only"])

        scan_layout.addWidget(scan_label)
        scan_layout.addStretch()
        scan_layout.addWidget(scan_combo)

        save_btn = QPushButton("💾 Save Settings")
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
        layout.setSpacing(18)

        ai_title = QLabel("AI Model Preferences")
        ai_title.setStyleSheet("font-size: 18px; font-weight: 600;")
        ai_subtitle = QLabel("Choose and configure AI models for different tasks")
        ai_subtitle.setStyleSheet("font-size: 13px; margin-bottom: 10px;")

        layout.addWidget(ai_title)
        layout.addWidget(ai_subtitle)

        model_card = QFrame()
        model_card.setStyleSheet("""
            QFrame { border-radius: 12px; border: 1px solid #2b3548; padding: 10px; }
        """)
        model_layout = QVBoxLayout(model_card)
        model_layout.setContentsMargins(20, 20, 20, 20)
        model_layout.setSpacing(12)

        primary_layout = QHBoxLayout()
        primary_label = QLabel("Primary AI Model")
        primary_label.setStyleSheet("font-size: 14px;")
        self.model_combo = QComboBox()
        # UPDATED: Use model keys from shared AI instance if available
        if self.ai:
            model_keys = list(self.ai.MODELS.keys())
        else:
            model_keys = ["phi3-mini", "mistral-7b", "deepseek-1.5b", "qwen2.5-1.5b"]
        self.model_combo.addItems(model_keys)
        current = self.settings.get("default_model", "phi3-mini")
        idx = model_keys.index(current) if current in model_keys else 0
        self.model_combo.setCurrentIndex(idx)
        primary_layout.addWidget(primary_label)
        primary_layout.addStretch()
        primary_layout.addWidget(self.model_combo)
        model_layout.addLayout(primary_layout)

        # Model info box
        self.model_info_frame = QFrame()
        self.model_info_frame.setStyleSheet("QFrame { border: 1px solid #2b3548; border-radius: 8px; padding: 8px; }")
        info_layout = QVBoxLayout(self.model_info_frame)
        info_layout.setContentsMargins(12, 12, 12, 12)
        self.model_info_label = QLabel()
        self.model_info_label.setWordWrap(True)
        info_layout.addWidget(self.model_info_label)
        model_layout.addWidget(self.model_info_frame)
        self.update_model_info(self.model_combo.currentText())
        self.model_combo.currentTextChanged.connect(self.update_model_info)

        # Advanced settings (embedded)
        adv_card = QFrame()
        adv_card.setStyleSheet("QFrame { border-radius: 10px; border: 1px dashed #2b3548; padding: 10px; }")
        adv_layout = QVBoxLayout(adv_card)
        adv_layout.setContentsMargins(12, 12, 12, 12)
        adv_layout.setSpacing(10)

        adv_title = QLabel("Advanced Model Settings")
        adv_title.setStyleSheet("font-weight: 600; font-size: 14px;")
        adv_layout.addWidget(adv_title)

        form = QFormLayout()
        # Max tokens (spin box)
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(32, 4096)
        self.max_tokens_spin.setValue(int(self.settings.get("max_tokens", 256)))
        form.addRow("Max Tokens:", self.max_tokens_spin)

        # Temperature slider (0.0 - 2.0)
        temp_row = QHBoxLayout()
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(10, 200)  # map to 0.1 - 2.0
        self.temp_slider.setValue(int(self.settings.get("temperature", 0.7) * 100))
        self.temp_label = QLabel(f"{self.settings.get('temperature', 0.7):.2f}")
        self.temp_slider.valueChanged.connect(lambda v: self.temp_label.setText(f"{v/100:.2f}"))
        temp_row.addWidget(self.temp_slider)
        temp_row.addWidget(self.temp_label)
        form.addRow("Temperature:", temp_row)

        # Top-p slider
        top_p_row = QHBoxLayout()
        self.top_p_slider = QSlider(Qt.Horizontal)
        self.top_p_slider.setRange(0, 100)
        self.top_p_slider.setValue(int(self.settings.get("top_p", 0.9) * 100))
        self.top_p_label = QLabel(f"{self.settings.get('top_p', 0.9):.2f}")
        self.top_p_slider.valueChanged.connect(lambda v: self.top_p_label.setText(f"{v/100:.2f}"))
        top_p_row.addWidget(self.top_p_slider)
        top_p_row.addWidget(self.top_p_label)
        form.addRow("Top-P:", top_p_row)

        # System prompt editor
        self.system_prompt_edit = QTextEdit()
        self.system_prompt_edit.setPlaceholderText("System prompt for SARA (persisted)")
        self.system_prompt_edit.setMaximumHeight(120)
        self.system_prompt_edit.setPlainText(self.settings.get("system_prompt", ""))

        # Force CPU toggle
        self.force_cpu_check = QCheckBox("Force CPU mode (disable GPU)")
        self.force_cpu_check.setChecked(bool(self.settings.get("force_cpu", False)))

        # VRAM budget combo
        self.vram_combo = QComboBox()
        vram_options = ["No Limit", "2 GB", "4 GB", "6 GB", "8 GB"]
        self.vram_combo.addItems(vram_options)
        current_limit = self.settings.get("vram_limit_gb", None)
        if current_limit is None:
            self.vram_combo.setCurrentIndex(0)
        else:
            # choose nearest
            mapping = {2:1,4:2,6:3,8:4}
            idx = mapping.get(int(current_limit), 0)
            self.vram_combo.setCurrentIndex(idx)

        # Idle unload
        idle_layout = QHBoxLayout()
        idle_label = QLabel("Auto-unload after (minutes):")
        self.idle_spin = QSpinBox()
        self.idle_spin.setRange(0, 240)
        self.idle_spin.setValue(int(self.settings.get("idle_unload_seconds", 600) / 60))
        idle_layout.addWidget(idle_label)
        idle_layout.addStretch()
        idle_layout.addWidget(self.idle_spin)

        # Apply button
        apply_btn = QPushButton("Apply Model Settings")
        apply_btn.clicked.connect(self.apply_ai_settings)

        adv_layout.addLayout(form)
        adv_layout.addWidget(QLabel("System Prompt:"))
        adv_layout.addWidget(self.system_prompt_edit)
        adv_layout.addWidget(self.force_cpu_check)
        adv_layout.addLayout(idle_layout)
        adv_layout.addWidget(QLabel("VRAM Budget:"))
        adv_layout.addWidget(self.vram_combo)
        adv_layout.addWidget(apply_btn)

        model_layout.addWidget(adv_card)
        layout.addWidget(model_card)
        layout.addStretch()
        widget.setLayout(layout)
        return widget

    # ==================== SCRIPTS TAB ====================
    def create_scripts_tab(self):
        widget = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        scripts_title = QLabel("Script Library Management")
        scripts_subtitle = QLabel("Manage custom scripts for specialized system operations")
        layout.addWidget(scripts_title)
        layout.addWidget(scripts_subtitle)

        add_card = QFrame()
        add_card.setStyleSheet("QFrame {border-radius:12px;border:1px solid #2b3548;padding:10px;}")
        add_layout = QVBoxLayout(add_card)
        add_layout.setContentsMargins(20,20,20,20)
        add_layout.setSpacing(12)

        name_label = QLabel("Script Name")
        self.script_name_input = QLineEdit()
        desc_label = QLabel("Description")
        self.script_desc_input = QTextEdit()
        self.script_desc_input.setMaximumHeight(80)

        add_btn = QPushButton("+ Add Script")
        add_btn.clicked.connect(self.add_script)

        add_layout.addWidget(name_label)
        add_layout.addWidget(self.script_name_input)
        add_layout.addWidget(desc_label)
        add_layout.addWidget(self.script_desc_input)
        add_layout.addWidget(add_btn)

        layout.addWidget(add_card)

        scripts_data = [
            ("Advanced Registry Cleaner", "Maintenance", "Comprehensive registry cleanup and optimization", "2025-09-23"),
            ("Network Diagnostics", "Network", "Diagnose and fix network connectivity issues", "2025-09-22"),
            ("GPU Performance Test", "Hardware", "Test graphics card performance and stability", "2025-09-21"),
        ]

        for name, category, desc, last_used in scripts_data:
            script_card = self.create_script_card(name, category, desc, last_used)
            layout.addWidget(script_card)

        layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout = QVBoxLayout(widget)
        main_layout.addWidget(scroll)
        return widget

    def create_script_card(self, name, category, description, last_used):
        card = QFrame()
        card.setStyleSheet("QFrame { border-radius: 12px; border: 1px solid #2b3548; padding: 10px; }")
        layout = QVBoxLayout(card)
        header_layout = QHBoxLayout()
        name_label = QLabel(name)
        category_badge = QLabel(category)
        category_badge.setStyleSheet("background: #2b3548; color: #9eb3ff; padding: 4px 10px; border-radius:6px; font-weight:600;")
        header_layout.addWidget(name_label)
        header_layout.addWidget(category_badge)
        header_layout.addStretch()

        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        last_used_label = QLabel(f"Last used: {last_used}")
        last_used_label.setStyleSheet("font-size:12px; font-style:italic; opacity:0.7;")
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        edit_btn = QPushButton("✏️ Edit")
        delete_btn = QPushButton("🗑️ Delete")
        btn_layout.addWidget(edit_btn)
        btn_layout.addWidget(delete_btn)

        layout.addLayout(header_layout)
        layout.addWidget(desc_label)
        layout.addWidget(last_used_label)
        layout.addLayout(btn_layout)
        return card

    # ==================== EVENT HANDLERS ====================
    def on_theme_changed(self, theme_text):
        if theme_text == "Dark Mode":
            self.current_theme = "dark"
        else:
            self.current_theme = "light"
        self.theme_changed.emit(self.current_theme)

    def save_general_settings(self):
        # write whatever general settings you want persisted
        self.settings["notifications"] = self.notif_check.isChecked()
        self.settings["auto_updates"] = self.updates_check.isChecked()
        self.settings["auto_scan"] = self.auto_scan_check.isChecked()
        self.save_settings_file(self.settings)
        print("Settings saved!")

    def update_model_info(self, model_name):
        # provide helpful text for model keys
        info = {
            "phi3-mini": "<b>Phi-3.5 Mini (phi3-mini)</b><br>Fast, low VRAM — great for log parsing and sysadmin tasks.",
            "mistral-7b": "<b>Mistral 7B (mistral-7b)</b><br>Powerful & balanced, good for more nuanced reasoning.",
            "deepseek-1.5b": "<b>DeepSeek 1.5B</b><br>Very lightweight, fast local parsing and short answers.",
            "qwen2.5-1.5b": "<b>Qwen 2.5B</b><br>Ultra-light, great for small tasks and prototypes."
        }
        self.model_info_label.setText(info.get(model_name, "Unknown model"))

    def apply_ai_settings(self):
        # build settings dict from UI
        vram_idx = self.vram_combo.currentIndex()
        vram_map = {0: None, 1:2, 2:4, 3:6, 4:8}
        
        sg = {
            "default_model": self.model_combo.currentText(),
            "force_cpu": self.force_cpu_check.isChecked(),
            "vram_limit_gb": vram_map.get(vram_idx, None),
            "idle_unload_seconds": int(self.idle_spin.value() * 60),
            "max_tokens": int(self.max_tokens_spin.value()),
            "temperature": float(self.temp_slider.value() / 100.0),
            "top_p": float(self.top_p_slider.value() / 100.0),
            "system_prompt": self.system_prompt_edit.toPlainText()
        }
        # merge into settings & persist
        self.settings.update(sg)
        self.save_settings_file(self.settings)
        
        # UPDATED: Apply to shared AI instance if available
        if self.ai:
            self.ai.set_force_cpu(self.settings.get("force_cpu", False))
            self.ai.set_vram_limit(self.settings.get("vram_limit_gb", None))
            self.ai.idle_unload_seconds = int(self.settings.get("idle_unload_seconds", 600))
            # optionally switch model
            default_model = self.settings.get("default_model")
            if default_model and default_model in self.ai.MODELS:
                self.ai.switch_model(default_model)
        
        # emit the settings to interested components
        self.ai_settings_changed.emit(self.settings)
        print("AI model settings applied and saved.")

    def add_script(self):
        name = self.script_name_input.text().strip()
        desc = self.script_desc_input.toPlainText().strip()
        if not name or not desc:
            print("Please fill in both script name and description")
            return
        print(f"Adding script: {name}")
        self.script_name_input.clear()
        self.script_desc_input.clear()