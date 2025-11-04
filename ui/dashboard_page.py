from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout

class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(25)

        title = QLabel("📊 Dashboard")
        title.setObjectName("title")
        subtitle = QLabel("System overview and quick stats")
        subtitle.setObjectName("subtitle")

        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Example system info cards
        row = QHBoxLayout()
        row.setSpacing(20)
        row.addWidget(self.create_card("System Status", "All systems operational"))
        row.addWidget(self.create_card("Last Maintenance", "2 days ago"))
        row.addWidget(self.create_card("Performance Score", "96%"))

        layout.addLayout(row)
        layout.addStretch()
        self.setLayout(layout)

    def create_card(self, title, description):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #1b2230;
                border-radius: 12px;
                border: 1px solid #2b3548;
            }
        """)
        vbox = QVBoxLayout(card)
        vbox.setContentsMargins(20, 20, 20, 20)
        vbox.setSpacing(6)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-size: 16px; font-weight: 600; color: white;")
        d_lbl = QLabel(description)
        d_lbl.setStyleSheet("color: #cfd7ff; font-size: 13px;")

        vbox.addWidget(t_lbl)
        vbox.addWidget(d_lbl)
        return card
