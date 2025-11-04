from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QCheckBox, QPushButton

class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(25)

        title = QLabel("⚙️ Settings")
        title.setObjectName("title")
        subtitle = QLabel("Customize your SARA preferences and behavior")
        subtitle.setObjectName("subtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        settings_card = QFrame()
        settings_card.setStyleSheet("""
            QFrame {
                background: #1b2230;
                border-radius: 12px;
                border: 1px solid #2b3548;
            }
        """)
        inner = QVBoxLayout(settings_card)
        inner.setContentsMargins(20, 20, 20, 20)
        inner.setSpacing(12)

        dark = QCheckBox("Enable Dark Mode")
        notif = QCheckBox("Enable Notifications")
        updates = QCheckBox("Automatically Check for Updates")

        save_btn = QPushButton("💾 Save Settings")
        save_btn.setStyleSheet("""
            QPushButton {
                background: #6e8bff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 600;
            }
            QPushButton:hover { background: #869eff; }
        """)

        inner.addWidget(dark)
        inner.addWidget(notif)
        inner.addWidget(updates)
        inner.addStretch()
        inner.addWidget(save_btn)

        layout.addWidget(settings_card)
        layout.addStretch()
        self.setLayout(layout)
