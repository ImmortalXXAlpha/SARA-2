# ui/main_window.py
from PySide6.QtWidgets import (
    QWidget, QStackedWidget, QVBoxLayout, QPushButton, QHBoxLayout,
    QFrame, QSpacerItem, QSizePolicy, QComboBox, QLabel
)
from PySide6.QtGui import QColor, QPalette
from PySide6.QtCore import Qt

# Import pages
from .dashboard_page import DashboardPage
from .clean_tune_page import CleanTunePage
from .hardware_page import HardwarePage
from .ai_console_page import AIConsolePage
from .reports_page import ReportsPage
from .settings_page import SettingsPage

# Import NovaAI
from ai.nova_ai import NovaAI

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SARA — AI Repair Agent")
        self.resize(1300, 750)

        # accents and theme
        self.accents = {"Blue":"#6e8bff","Purple":"#9b6eff","Green":"#4ef57a","Red":"#ff6e6e"}
        self.current_accent = self.accents["Blue"]
        self.current_theme = "dark"

        # create the central NovaAI instance
        # choose default model by VRAM auto-selection if desired
        self.ai = NovaAI(model_key="phi3-mini")
        # wire optional UI-level callbacks (MainWindow may handle high-level updates)
        # We'll pass ai into pages below

        # Build UI and pages (pass ai instance where needed)
        self.build_ui()

        self.apply_theme(self.current_accent, self.current_theme)

        # connect settings theme change
        self.pages["Settings"].theme_changed.connect(self.handle_theme_change)

        # connect ai settings emitted from SettingsPage to apply to NovaAI
        self.pages["Settings"].ai_settings_changed.connect(self.apply_ai_settings_from_settings_page)

    def build_ui(self):
        self.stack = QStackedWidget()
        self.pages = {
            "Dashboard": DashboardPage(),
            "Clean Tune": CleanTunePage(),
            "Hardware": HardwarePage(),
            # pass shared ai into the AIConsole and Settings pages:
            "AI Console": AIConsolePage(ai=self.ai),
            "Reports": ReportsPage(),
            "Settings": SettingsPage(ai=self.ai)
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        # Sidebar
        sidebar_frame = QFrame()
        sidebar_frame.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setAlignment(Qt.AlignTop)
        sidebar_layout.setContentsMargins(8,24,8,24)
        sidebar_layout.setSpacing(14)

        # logo
        logo_label = QLabel("🤖 SARA"); logo_label.setStyleSheet("font-size:24px; font-weight:bold; color:#fff;")
        subtitle_label = QLabel("AI Repair Agent"); subtitle_label.setStyleSheet("color:#9eb3ff;")
        logo_container = QFrame(); logo_layout = QVBoxLayout(logo_container)
        logo_layout.addWidget(logo_label); logo_layout.addWidget(subtitle_label)
        sidebar_layout.addWidget(logo_container)

        self.buttons = {}
        for name in self.pages.keys():
            btn = QPushButton(name)
            btn.clicked.connect(lambda _, n=name: self.switch_page(n))
            sidebar_layout.addWidget(btn)
            self.buttons[name] = btn

        sidebar_layout.addItem(QSpacerItem(20,40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        accent_label = QLabel("Accent Color"); accent_label.setStyleSheet("color:#9eb3ff; font-size:12px;")
        sidebar_layout.addWidget(accent_label)
        accent_box = QComboBox(); accent_box.addItems(self.accents.keys()); accent_box.setCurrentText("Blue")
        accent_box.currentTextChanged.connect(self.change_accent)
        sidebar_layout.addWidget(accent_box)

        layout = QHBoxLayout(self)
        layout.addWidget(sidebar_frame, 1)
        layout.addWidget(self.stack, 5)
        layout.setSpacing(0); layout.setContentsMargins(0,0,0,0)
        self.switch_page("Dashboard")

    def switch_page(self, name):
        self.stack.setCurrentWidget(self.pages[name])
        accent = self.current_accent
        for n, btn in self.buttons.items():
            if n == name:
                btn.setStyleSheet(f"background:{accent}; color:white; border-radius:10px; font-weight:700;")
            else:
                btn.setStyleSheet("")

    def change_accent(self, accent_name):
        self.current_accent = self.accents.get(accent_name, self.current_accent)
        self.apply_theme(self.current_accent, self.current_theme)
        for page in self.pages.values():
            page.setStyleSheet(self.styleSheet())

    def handle_theme_change(self, theme):
        self.current_theme = theme
        self.apply_theme(self.current_accent, self.current_theme)
        for page in self.pages.values():
            page.setStyleSheet(self.styleSheet())

    def apply_theme(self, accent, theme):
        """Apply theme styling based on accent color and theme mode (dark/light)"""
        if theme == "dark":
            bg_main = "#0f1117"
            bg_card = "#1b2230"
            text_primary = "#e8eef6"
            text_secondary = "#cfd7ff"
            border_color = "#2b3548"
        else:  # light mode
            bg_main = "#f5f7fa"
            bg_card = "#ffffff"
            text_primary = "#1a1d29"
            text_secondary = "#4a5568"
            border_color = "#e2e8f0"
        
        # Build stylesheet with theme colors
        style = f"""
            QWidget {{
                background-color: {bg_main};
                color: {text_primary};
            }}
            QFrame#sidebar {{
                background-color: {bg_card};
                border-right: 1px solid {border_color};
            }}
            QLabel#title {{
                font-size: 28px;
                font-weight: 700;
                color: {text_primary};
            }}
            QLabel#subtitle {{
                font-size: 14px;
                color: {text_secondary};
            }}
            QPushButton {{
                background-color: {bg_card};
                color: {text_primary};
                border: 1px solid {border_color};
                border-radius: 10px;
                padding: 8px 14px;
                text-align: left;
            }}
            QPushButton:hover {{
                background-color: {accent};
                border-color: {accent};
                color: white;
            }}
        """
        self.setStyleSheet(style)

    def apply_ai_settings_from_settings_page(self, settings):
        # settings from SettingsPage applied to NovaAI
        if not self.ai:
            return
        self.ai.set_force_cpu(bool(settings.get("force_cpu", False)))
        self.ai.set_vram_limit(settings.get("vram_limit_gb", None))
        self.ai.idle_unload_seconds = int(settings.get("idle_unload_seconds", 600))
        # if default model changed, switch
        default_model = settings.get("default_model")
        if default_model and default_model in self.ai.MODELS:
            self.ai.switch_model(default_model)