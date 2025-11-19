from PySide6.QtWidgets import (
    QWidget, QStackedWidget, QVBoxLayout, QPushButton, QHBoxLayout,
    QFrame, QSpacerItem, QSizePolicy, QComboBox, QLabel
)
from PySide6.QtGui import QColor, QPalette
from PySide6.QtCore import Qt
from ui.dashboard_page import DashboardPage
from ui.clean_tune_page import CleanTunePage
from ui.hardware_page import HardwarePage
from ui.ai_console_page import AIConsolePage
from ui.reports_page import ReportsPage
from ui.settings_page import SettingsPage


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SARA — AI Repair Agent")
        self.resize(1300, 750)

        # 🎨 Accent color options
        self.accents = {
            "Blue": "#6e8bff",
            "Purple": "#9b6eff",
            "Green": "#4ef57a",
            "Red": "#ff6e6e"
        }
        self.current_accent = self.accents["Blue"]
        self.current_theme = "dark"  # Track theme

        # Build UI first
        self.build_ui()
        
        # Apply initial theme
        self.apply_theme(self.current_accent, self.current_theme)
        
        # Connect settings page theme signal
        self.pages["Settings"].theme_changed.connect(self.handle_theme_change)

    # 💡 Apply theme with light/dark mode support
    def apply_theme(self, accent, theme="dark"):
        if theme == "dark":
            bg_main = "#0f1117"
            bg_sidebar = "#141922"
            bg_sidebar_end = "#1e2635"
            bg_card = "#1b2230"
            bg_input = "#0f1522"
            bg_progress = "#131a28"
            text_primary = "#e8eef6"
            text_secondary = "#b4c2e2"
            text_tertiary = "#8aa0ff"
            border_color = "#2b3548"
            card_border = "#2b3548"
        else:  # light mode
            bg_main = "#f5f7fa"
            bg_sidebar = "#e8ecf1"
            bg_sidebar_end = "#d4dce6"
            bg_card = "#ffffff"
            bg_input = "#ffffff"
            bg_progress = "#e8ecf1"
            text_primary = "#1a2332"
            text_secondary = "#4a5568"
            text_tertiary = "#5a6b7f"
            border_color = "#cbd5e0"
            card_border = "#e2e8f0"

        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(bg_main))
        palette.setColor(QPalette.WindowText, QColor(text_primary))
        self.setPalette(palette)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_main};
                color: {text_primary};
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px;
            }}

            /* Sidebar styling */
            QFrame#sidebar {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {bg_sidebar}, stop:1 {bg_sidebar_end});
                border-right: 1px solid {border_color};
            }}

            QPushButton {{
                background: {bg_card};
                color: {text_primary};
                border: 1px solid {border_color};
                border-radius: 10px;
                padding: 10px 14px;
                margin: 8px 14px;
                text-align: left;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {accent};
                border-color: {accent};
                color: #ffffff;
            }}
            QPushButton:pressed {{
                background: {bg_input};
                border-color: {accent};
            }}

            /* Titles & Subtitles */
            QLabel#title {{
                font-size: 28px;
                font-weight: 700;
                color: {text_primary};
                margin-bottom: 4px;
            }}

            QLabel#subtitle {{
                color: {text_secondary};
                font-size: 15px;
                font-weight: 500;
                margin-bottom: 12px;
            }}

            /* Cards and Frames */
            QFrame {{
                color: {text_primary};
            }}

            /* Progress bars */
            QProgressBar {{
                background: {bg_progress};
                border: 1px solid {border_color};
                border-radius: 8px;
                text-align: center;
                color: {text_primary};
                min-height: 8px;
            }}
            QProgressBar::chunk {{
                background: {accent};
                border-radius: 8px;
            }}

            /* ComboBox */
            QComboBox {{
                background: {bg_card};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 6px 10px;
                color: {text_primary};
                font-weight: 500;
            }}
            QComboBox::drop-down {{
                border: none;
            }}
            QComboBox QAbstractItemView {{
                background: {bg_card};
                border: 1px solid {border_color};
                selection-background-color: {accent};
                selection-color: white;
            }}

            /* TextEdit and LineEdit */
            QTextEdit, QLineEdit {{
                background: {bg_input};
                color: {text_primary};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 6px;
            }}
            QTextEdit:focus, QLineEdit:focus {{
                border-color: {accent};
            }}

            /* CheckBox */
            QCheckBox {{
                color: {text_primary};
            }}

            /* TabWidget */
            QTabWidget::pane {{
                border: 1px solid {border_color};
                border-radius: 8px;
                background: {bg_card};
            }}
            QTabBar::tab {{
                background: {bg_input};
                color: {text_secondary};
                padding: 10px 20px;
                border: 1px solid {border_color};
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {bg_card};
                color: {text_primary};
                border-color: {accent};
            }}
            QTabBar::tab:hover {{
                background: {bg_card};
            }}

            /* ScrollBar */
            QScrollBar:vertical {{
                width: 10px;
                background: {bg_input};
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background: {border_color};
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {accent};
            }}

            /* ListWidget */
            QListWidget {{
                background: {bg_input};
                border: 1px solid {border_color};
                border-radius: 8px;
                color: {text_primary};
            }}
            QListWidget::item:selected {{
                background: {accent};
                color: white;
            }}
        """)

    # ⚙️ Builds main window layout
    def build_ui(self):
        # Stacked pages
        self.stack = QStackedWidget()
        self.pages = {
            "Dashboard": DashboardPage(),
            "Clean Tune": CleanTunePage(),
            "Hardware": HardwarePage(),
            "AI Console": AIConsolePage(),
            "Reports": ReportsPage(),
            "Settings": SettingsPage()
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        # Sidebar (with spacing + accent switcher)
        sidebar_frame = QFrame()
        sidebar_frame.setObjectName("sidebar")
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setAlignment(Qt.AlignTop)
        sidebar_layout.setContentsMargins(8, 24, 8, 24)
        sidebar_layout.setSpacing(14)

        # Logo section
        logo_container = QWidget()
        logo_layout = QVBoxLayout(logo_container)
        logo_layout.setContentsMargins(14, 10, 14, 20)
        
        logo_label = QLabel("🤖 SARA")
        logo_label.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #ffffff;
            background: transparent;
        """)
        
        subtitle_label = QLabel("AI Repair Agent")
        subtitle_label.setStyleSheet("""
            font-size: 13px;
            color: #9eb3ff;
            background: transparent;
        """)
        
        logo_layout.addWidget(logo_label)
        logo_layout.addWidget(subtitle_label)
        sidebar_layout.addWidget(logo_container)

        # Sidebar Buttons
        self.buttons = {}
        for name in self.pages.keys():
            btn = QPushButton(name)
            btn.clicked.connect(lambda _, n=name: self.switch_page(n))
            sidebar_layout.addWidget(btn)
            self.buttons[name] = btn

        # Spacer and accent selector
        sidebar_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))
        
        # Accent color selector
        accent_label = QLabel("Accent Color")
        accent_label.setStyleSheet("color: #9eb3ff; font-size: 12px; margin-left: 14px; background: transparent;")
        sidebar_layout.addWidget(accent_label)
        
        accent_box = QComboBox()
        accent_box.addItems(self.accents.keys())
        accent_box.setCurrentText("Blue")
        accent_box.currentTextChanged.connect(self.change_accent)
        accent_box.setStyleSheet("""
            QComboBox {
                margin: 0px 14px 14px 14px;
            }
        """)
        sidebar_layout.addWidget(accent_box)

        # Main layout: sidebar + stacked widget
        layout = QHBoxLayout(self)
        layout.addWidget(sidebar_frame, 1)
        layout.addWidget(self.stack, 5)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        self.switch_page("Dashboard")

    def switch_page(self, name):
        """Switch active content page and visually highlight sidebar button."""
        self.stack.setCurrentWidget(self.pages[name])
        accent = self.current_accent

        # Update button highlighting
        for n, btn in self.buttons.items():
            if n == name:
                btn.setStyleSheet(f"""
                    background: {accent};
                    color: white;
                    border-radius: 10px;
                    font-weight: 700;
                    border: 1px solid {accent};
                    padding: 10px 14px;
                    margin: 8px 14px;
                    text-align: left;
                """)
            else:
                # Will use default button style from main theme
                btn.setStyleSheet("")

    def change_accent(self, accent_name):
        """Change accent color dynamically."""
        self.current_accent = self.accents[accent_name]
        self.apply_theme(self.current_accent, self.current_theme)
        
        # Re-apply style to all pages
        for page in self.pages.values():
            page.setStyleSheet(self.styleSheet())
        
        # Keep sidebar highlight consistent
        current_name = [k for k, v in self.pages.items() if v == self.stack.currentWidget()]
        if current_name:
            self.switch_page(current_name[0])

    def handle_theme_change(self, theme):
        """Handle theme change from settings page."""
        self.current_theme = theme
        self.apply_theme(self.current_accent, self.current_theme)
        
        # Re-apply style to all pages
        for page in self.pages.values():
            page.setStyleSheet(self.styleSheet())
        
        # Keep sidebar highlight consistent
        current_name = [k for k, v in self.pages.items() if v == self.stack.currentWidget()]
        if current_name:
            self.switch_page(current_name[0])
        
        print(f"✅ Theme switched to: {theme} mode with {self.current_accent} accent")