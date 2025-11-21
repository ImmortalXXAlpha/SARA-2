# ui/main_window.py
"""
Optimized MainWindow with lazy page loading and AI-tool integration.
Key optimizations:
- Lazy page instantiation (pages created on first access)
- Reduced stylesheet recalculations
- Shared AI instance properly wired to tools
- Efficient signal connections
"""

from PySide6.QtWidgets import (
    QWidget, QStackedWidget, QVBoxLayout, QPushButton, QHBoxLayout,
    QFrame, QSpacerItem, QSizePolicy, QComboBox, QLabel
)
from PySide6.QtCore import Qt, QTimer
from typing import Dict, Optional

# Import NovaAI
from ai.nova_ai import NovaAI


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SARA — AI Repair Agent")
        self.resize(1300, 750)

        # Theme settings
        self.accents = {"Blue": "#6e8bff", "Purple": "#9b6eff", "Green": "#4ef57a", "Red": "#ff6e6e"}
        self.current_accent = self.accents["Blue"]
        self.current_theme = "dark"

        # Create the central NovaAI instance
        self.ai = NovaAI(model_key="phi3-mini")

        # Lazy page loading - pages dict stores either class or instance
        self._page_classes: Dict[str, type] = {}
        self._page_instances: Dict[str, QWidget] = {}
        self._pages_initialized = False

        # Build UI
        self._build_ui()
        self._apply_theme(self.current_accent, self.current_theme)

        # Defer page initialization to after window shows (faster startup)
        QTimer.singleShot(50, self._initialize_pages)

    def _build_ui(self):
        """Build the main UI structure."""
        self.stack = QStackedWidget()

        # Sidebar
        sidebar_frame = QFrame()
        sidebar_frame.setObjectName("sidebar")
        sidebar_frame.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setAlignment(Qt.AlignTop)
        sidebar_layout.setContentsMargins(8, 24, 8, 24)
        sidebar_layout.setSpacing(14)

        # Logo
        logo_label = QLabel("🤖 SARA")
        logo_label.setStyleSheet("font-size:24px; font-weight:bold; color:#fff;")
        subtitle_label = QLabel("AI Repair Agent")
        subtitle_label.setStyleSheet("color:#9eb3ff;")
        logo_container = QFrame()
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(10, 0, 0, 20)
        logo_layout.addWidget(logo_label)
        logo_layout.addWidget(subtitle_label)
        sidebar_layout.addWidget(logo_container)

        # Navigation buttons
        self.buttons: Dict[str, QPushButton] = {}
        nav_items = ["Dashboard", "Clean Tune", "Hardware", "AI Console", "Reports", "Settings"]
        
        for name in nav_items:
            btn = QPushButton(name)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _, n=name: self._switch_page(n))
            sidebar_layout.addWidget(btn)
            self.buttons[name] = btn

        sidebar_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        # Accent selector
        accent_label = QLabel("Accent Color")
        accent_label.setStyleSheet("color:#9eb3ff; font-size:12px;")
        sidebar_layout.addWidget(accent_label)
        
        accent_box = QComboBox()
        accent_box.addItems(self.accents.keys())
        accent_box.setCurrentText("Blue")
        accent_box.currentTextChanged.connect(self._change_accent)
        sidebar_layout.addWidget(accent_box)

        # Main layout
        layout = QHBoxLayout(self)
        layout.addWidget(sidebar_frame)
        layout.addWidget(self.stack, 1)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

    def _initialize_pages(self):
        """Initialize pages lazily - import and create only when needed."""
        if self._pages_initialized:
            return
            
        # Import page classes here to speed up initial window display
        from .dashboard_page import DashboardPage
        from .clean_tune_page import CleanTunePage
        from .hardware_page import HardwarePage
        from .ai_console_page import AIConsolePage
        from .reports_page import ReportsPage
        from .settings_page import SettingsPage

        # Store classes for lazy instantiation
        self._page_classes = {
            "Dashboard": DashboardPage,
            "Clean Tune": CleanTunePage,
            "Hardware": HardwarePage,
            "AI Console": AIConsolePage,
            "Reports": ReportsPage,
            "Settings": SettingsPage,
        }
        
        # Create critical pages immediately
        self._get_or_create_page("Dashboard")
        self._get_or_create_page("Clean Tune")  # Needed for AI integration
        
        # Wire AI Console to Clean Tune
        ai_console = self._get_or_create_page("AI Console")
        clean_tune = self._page_instances.get("Clean Tune")
        if ai_console and clean_tune:
            ai_console.set_clean_tune_page(clean_tune)
        
        # Wire settings
        settings = self._get_or_create_page("Settings")
        if settings:
            settings.theme_changed.connect(self._handle_theme_change)
            settings.ai_settings_changed.connect(self._apply_ai_settings)

        self._pages_initialized = True
        self._switch_page("Dashboard")

    def _get_or_create_page(self, name: str) -> Optional[QWidget]:
        """Get existing page or create it lazily."""
        if name in self._page_instances:
            return self._page_instances[name]
            
        if name not in self._page_classes:
            return None
            
        page_class = self._page_classes[name]
        
        # Special handling for pages that need AI instance
        if name == "AI Console":
            clean_tune = self._page_instances.get("Clean Tune")
            page = page_class(ai=self.ai, clean_tune_page=clean_tune)
        elif name == "Settings":
            page = page_class(ai=self.ai)
        else:
            page = page_class()
            
        self._page_instances[name] = page
        self.stack.addWidget(page)
        return page

    def _switch_page(self, name: str):
        """Switch to a page, creating it if necessary."""
        page = self._get_or_create_page(name)
        if page:
            self.stack.setCurrentWidget(page)
            
        # Update button styles
        accent = self.current_accent
        for n, btn in self.buttons.items():
            if n == name:
                btn.setStyleSheet(f"""
                    background: {accent}; 
                    color: white; 
                    border-radius: 10px; 
                    font-weight: 700;
                    border: none;
                """)
            else:
                btn.setStyleSheet("")

    def _change_accent(self, accent_name: str):
        """Change the accent color."""
        self.current_accent = self.accents.get(accent_name, self.current_accent)
        self._apply_theme(self.current_accent, self.current_theme)

    def _handle_theme_change(self, theme: str):
        """Handle theme change from settings."""
        self.current_theme = theme
        self._apply_theme(self.current_accent, self.current_theme)

    def _apply_theme(self, accent: str, theme: str):
        """Apply theme styling efficiently."""
        if theme == "dark":
            bg_main, bg_card = "#0f1117", "#1b2230"
            text_primary, text_secondary = "#e8eef6", "#cfd7ff"
            border_color = "#2b3548"
        else:
            bg_main, bg_card = "#f5f7fa", "#ffffff"
            text_primary, text_secondary = "#1a1d29", "#4a5568"
            border_color = "#e2e8f0"

        style = f"""
            QWidget {{
                background-color: {bg_main};
                color: {text_primary};
                font-family: 'Segoe UI', sans-serif;
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
                padding: 10px 14px;
                text-align: left;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {accent};
                border-color: {accent};
                color: white;
            }}
            QComboBox {{
                background: {bg_card};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 6px 10px;
                color: {text_primary};
            }}
            QProgressBar {{
                background: {border_color};
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background: {accent};
                border-radius: 4px;
            }}
        """
        self.setStyleSheet(style)

    def _apply_ai_settings(self, settings: dict):
        """Apply AI settings from the settings page."""
        if not self.ai:
            return
        self.ai.set_force_cpu(bool(settings.get("force_cpu", False)))
        self.ai.set_vram_limit(settings.get("vram_limit_gb"))
        self.ai.idle_unload_seconds = int(settings.get("idle_unload_seconds", 600))
        
        default_model = settings.get("default_model")
        if default_model and default_model in self.ai.MODELS and default_model != self.ai.model_key:
            self.ai.switch_model(default_model)

    def closeEvent(self, event):
        """Clean shutdown of AI backend."""
        if self.ai:
            self.ai.shutdown()
        event.accept()