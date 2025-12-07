# ui/settings_page.py
"""
Settings Page with scrollable content.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QCheckBox, QPushButton,
    QTabWidget, QHBoxLayout, QComboBox, QLineEdit, QTextEdit,
    QScrollArea, QSlider, QFormLayout, QSpinBox, QGroupBox
)
from PySide6.QtCore import Qt, Signal
import json
import os


SCROLL_STYLE = """
    QScrollArea {
        border: none;
        background: transparent;
    }
    QScrollBar:vertical {
        background: #1b2230;
        width: 10px;
        border-radius: 5px;
        margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #3d4a6b;
        border-radius: 5px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background: #6e8bff;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0;
    }
"""


class SettingsPage(QWidget):
    theme_changed = Signal(str)
    ai_settings_changed = Signal(dict)

    def __init__(self, ai=None):
        super().__init__()
        self.ai = ai
        self.current_theme = "dark"
        self.settings_path = os.path.join(os.path.expanduser("~"), ".sara_settings.json")
        self.settings = self.load_settings()
        self._init_ui()

    def load_settings(self):
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
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

    def save_settings_file(self):
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Settings save error: {e}")

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        title = QLabel("⚙️ Settings")
        title.setObjectName("title")
        subtitle = QLabel("Customize SARA preferences and AI behavior")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        tabs = QTabWidget()
        tabs.addTab(self._create_general_tab(), "⚙️ General")
        tabs.addTab(self._create_ai_tab(), "🧠 AI Models")
        tabs.addTab(self._create_advanced_tab(), "🔧 Advanced")
        layout.addWidget(tabs)

    def _create_scrollable_tab(self, content_widget):
        """Wrap content in a scroll area."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(SCROLL_STYLE)
        scroll.setWidget(content_widget)
        return scroll

    def _create_general_tab(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Theme group
        theme_group = QGroupBox("Appearance")
        theme_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        theme_layout = QVBoxLayout(theme_group)
        
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme Mode:"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark Mode", "Light Mode"])
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        theme_row.addWidget(self.theme_combo)
        theme_row.addStretch()
        theme_layout.addLayout(theme_row)
        layout.addWidget(theme_group)

        # System group
        sys_group = QGroupBox("System Preferences")
        sys_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        sys_layout = QVBoxLayout(sys_group)
        
        self.notif_check = QCheckBox("Enable desktop notifications")
        self.notif_check.setChecked(self.settings.get("notifications", True))
        
        self.updates_check = QCheckBox("Check for updates automatically")
        self.updates_check.setChecked(self.settings.get("auto_updates", True))
        
        self.startup_check = QCheckBox("Start SARA with Windows")
        self.startup_check.setChecked(self.settings.get("start_with_windows", False))
        
        sys_layout.addWidget(self.notif_check)
        sys_layout.addWidget(self.updates_check)
        sys_layout.addWidget(self.startup_check)
        layout.addWidget(sys_group)

        # Save button
        save_btn = QPushButton("💾 Save General Settings")
        save_btn.clicked.connect(self._save_general)
        layout.addWidget(save_btn)
        
        layout.addStretch()
        return self._create_scrollable_tab(content)

    def _create_ai_tab(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Model selection group
        model_group = QGroupBox("Model Selection")
        model_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        model_layout = QVBoxLayout(model_group)
        
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Default Model:"))
        self.model_combo = QComboBox()
        if self.ai and hasattr(self.ai, 'MODELS'):
            self.model_combo.addItems(list(self.ai.MODELS.keys()))
        else:
            self.model_combo.addItems(["phi3-mini", "mistral-7b", "deepseek-1.5b", "qwen2.5-1.5b"])
        current = self.settings.get("default_model", "phi3-mini")
        idx = self.model_combo.findText(current)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        model_row.addWidget(self.model_combo)
        model_row.addStretch()
        model_layout.addLayout(model_row)
        
        # Model info
        self.model_info = QLabel()
        self.model_info.setWordWrap(True)
        self.model_info.setStyleSheet("color: #9eb3ff; padding: 10px; background: #0f1522; border-radius: 6px;")
        self._update_model_info(self.model_combo.currentText())
        self.model_combo.currentTextChanged.connect(self._update_model_info)
        model_layout.addWidget(self.model_info)
        
        layout.addWidget(model_group)

        # Generation settings group
        gen_group = QGroupBox("Generation Settings")
        gen_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        gen_layout = QFormLayout(gen_group)
        gen_layout.setSpacing(15)
        
        # Max tokens
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(32, 2048)
        self.max_tokens_spin.setValue(int(self.settings.get("max_tokens", 256)))
        gen_layout.addRow("Max Tokens:", self.max_tokens_spin)
        
        # Temperature
        temp_widget = QWidget()
        temp_layout = QHBoxLayout(temp_widget)
        temp_layout.setContentsMargins(0, 0, 0, 0)
        self.temp_slider = QSlider(Qt.Horizontal)
        self.temp_slider.setRange(10, 200)
        self.temp_slider.setValue(int(self.settings.get("temperature", 0.7) * 100))
        self.temp_label = QLabel(f"{self.settings.get('temperature', 0.7):.2f}")
        self.temp_label.setFixedWidth(40)
        self.temp_slider.valueChanged.connect(lambda v: self.temp_label.setText(f"{v/100:.2f}"))
        temp_layout.addWidget(self.temp_slider)
        temp_layout.addWidget(self.temp_label)
        gen_layout.addRow("Temperature:", temp_widget)
        
        # Top-P
        top_p_widget = QWidget()
        top_p_layout = QHBoxLayout(top_p_widget)
        top_p_layout.setContentsMargins(0, 0, 0, 0)
        self.top_p_slider = QSlider(Qt.Horizontal)
        self.top_p_slider.setRange(10, 100)
        self.top_p_slider.setValue(int(self.settings.get("top_p", 0.9) * 100))
        self.top_p_label = QLabel(f"{self.settings.get('top_p', 0.9):.2f}")
        self.top_p_label.setFixedWidth(40)
        self.top_p_slider.valueChanged.connect(lambda v: self.top_p_label.setText(f"{v/100:.2f}"))
        top_p_layout.addWidget(self.top_p_slider)
        top_p_layout.addWidget(self.top_p_label)
        gen_layout.addRow("Top-P:", top_p_widget)
        
        layout.addWidget(gen_group)

        # System prompt
        prompt_group = QGroupBox("System Prompt")
        prompt_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        prompt_layout = QVBoxLayout(prompt_group)
        
        self.system_prompt = QTextEdit()
        self.system_prompt.setPlaceholderText("Optional: Enter a custom system prompt for SARA...")
        self.system_prompt.setMaximumHeight(100)
        self.system_prompt.setPlainText(self.settings.get("system_prompt", ""))
        prompt_layout.addWidget(self.system_prompt)
        layout.addWidget(prompt_group)

        # Save button
        save_btn = QPushButton("💾 Save AI Settings")
        save_btn.clicked.connect(self._save_ai_settings)
        layout.addWidget(save_btn)
        
        layout.addStretch()
        return self._create_scrollable_tab(content)

    def _create_advanced_tab(self):
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Hardware group
        hw_group = QGroupBox("Hardware Settings")
        hw_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        hw_layout = QVBoxLayout(hw_group)
        
        self.force_cpu_check = QCheckBox("Force CPU mode (disable GPU acceleration)")
        self.force_cpu_check.setChecked(self.settings.get("force_cpu", False))
        hw_layout.addWidget(self.force_cpu_check)
        
        vram_row = QHBoxLayout()
        vram_row.addWidget(QLabel("VRAM Budget:"))
        self.vram_combo = QComboBox()
        self.vram_combo.addItems(["Auto (No Limit)", "2 GB", "4 GB", "6 GB", "8 GB", "12 GB"])
        vram_limit = self.settings.get("vram_limit_gb")
        if vram_limit:
            idx = {2: 1, 4: 2, 6: 3, 8: 4, 12: 5}.get(int(vram_limit), 0)
            self.vram_combo.setCurrentIndex(idx)
        vram_row.addWidget(self.vram_combo)
        vram_row.addStretch()
        hw_layout.addLayout(vram_row)
        
        layout.addWidget(hw_group)

        # Memory management group
        mem_group = QGroupBox("Memory Management")
        mem_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        mem_layout = QVBoxLayout(mem_group)
        
        idle_row = QHBoxLayout()
        idle_row.addWidget(QLabel("Auto-unload model after idle (minutes):"))
        self.idle_spin = QSpinBox()
        self.idle_spin.setRange(0, 240)
        self.idle_spin.setValue(int(self.settings.get("idle_unload_seconds", 600) / 60))
        self.idle_spin.setSpecialValueText("Never")
        idle_row.addWidget(self.idle_spin)
        idle_row.addStretch()
        mem_layout.addLayout(idle_row)
        
        mem_layout.addWidget(QLabel("Setting to 0 disables auto-unload (model stays in memory)"))
        
        layout.addWidget(mem_group)

        # Data group
        data_group = QGroupBox("Data & Storage")
        data_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        data_layout = QVBoxLayout(data_group)
        
        clear_cache_btn = QPushButton("🗑️ Clear Model Cache")
        clear_cache_btn.clicked.connect(self._clear_cache)
        data_layout.addWidget(clear_cache_btn)
        
        reset_btn = QPushButton("⚠️ Reset All Settings")
        reset_btn.setStyleSheet("QPushButton { color: #e74c3c; }")
        reset_btn.clicked.connect(self._reset_settings)
        data_layout.addWidget(reset_btn)
        
        layout.addWidget(data_group)

        # Save button
        save_btn = QPushButton("💾 Save Advanced Settings")
        save_btn.clicked.connect(self._save_advanced_settings)
        layout.addWidget(save_btn)
        
        layout.addStretch()
        return self._create_scrollable_tab(content)

    def _update_model_info(self, model_name):
        info = {
            "phi3-mini": "Phi-3.5 Mini - Fast and efficient, great for system tasks. ~3GB VRAM.",
            "mistral-7b": "Mistral 7B - Powerful reasoning, good for complex analysis. ~6GB VRAM.",
            "deepseek-1.5b": "DeepSeek 1.5B - Ultra-lightweight, very fast responses. ~2GB VRAM.",
            "qwen2.5-1.5b": "Qwen 2.5 1.5B - Compact and capable, good balance. ~1.5GB VRAM."
        }
        self.model_info.setText(info.get(model_name, "Unknown model"))

    def _on_theme_changed(self, text):
        self.current_theme = "dark" if "Dark" in text else "light"
        self.theme_changed.emit(self.current_theme)

    def _save_general(self):
        self.settings["notifications"] = self.notif_check.isChecked()
        self.settings["auto_updates"] = self.updates_check.isChecked()
        self.settings["start_with_windows"] = self.startup_check.isChecked()
        self.save_settings_file()
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Saved", "General settings saved!")

    def _save_ai_settings(self):
        self.settings["default_model"] = self.model_combo.currentText()
        self.settings["max_tokens"] = self.max_tokens_spin.value()
        self.settings["temperature"] = self.temp_slider.value() / 100.0
        self.settings["top_p"] = self.top_p_slider.value() / 100.0
        self.settings["system_prompt"] = self.system_prompt.toPlainText()
        self.save_settings_file()
        self.ai_settings_changed.emit(self.settings)
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Saved", "AI settings saved!")

    def _save_advanced_settings(self):
        self.settings["force_cpu"] = self.force_cpu_check.isChecked()
        vram_map = {0: None, 1: 2, 2: 4, 3: 6, 4: 8, 5: 12}
        self.settings["vram_limit_gb"] = vram_map.get(self.vram_combo.currentIndex())
        self.settings["idle_unload_seconds"] = self.idle_spin.value() * 60
        self.save_settings_file()
        self.ai_settings_changed.emit(self.settings)
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Saved", "Advanced settings saved!")

    def _clear_cache(self):
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, "Clear Cache", 
            "This will clear downloaded model files.\nYou'll need to re-download models.\n\nContinue?")
        if reply == QMessageBox.Yes:
            # Clear HuggingFace cache
            cache_dir = os.path.expanduser("~/.cache/huggingface")
            if os.path.exists(cache_dir):
                import shutil
                try:
                    shutil.rmtree(cache_dir)
                    QMessageBox.information(self, "Done", "Model cache cleared!")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Could not clear cache: {e}")

    def _reset_settings(self):
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.warning(self, "Reset Settings",
            "This will reset ALL settings to defaults.\n\nAre you sure?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.settings = {
                "default_model": "phi3-mini",
                "force_cpu": False,
                "vram_limit_gb": None,
                "idle_unload_seconds": 600,
                "max_tokens": 256,
                "temperature": 0.7,
                "top_p": 0.9,
                "system_prompt": ""
            }
            self.save_settings_file()
            QMessageBox.information(self, "Reset", "Settings reset to defaults. Please restart SARA.")