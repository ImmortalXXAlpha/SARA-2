# ui/dashboard_page.py
"""
Enhanced Dashboard with system overview, quick stats, and quick actions.
"""

import psutil
import platform
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout, 
    QGridLayout, QPushButton, QProgressBar
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap


class DashboardPage(QWidget):
    def __init__(self, ai=None, main_window=None):
        super().__init__()
        self.ai = ai
        self.main_window = main_window
        self._init_ui()
        
        # Auto-refresh stats every 5 seconds
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._update_stats)
        self.refresh_timer.start(5000)
        
        # Initial update
        self._update_stats()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(25)

        # ===== HEADER WITH LOGO =====
        header_layout = QHBoxLayout()
        
        # SARA Logo
        logo_label = QLabel()
        try:
            # Try to load SARA logo (adjust path as needed)
            pixmap = QPixmap("assets/SARA.png")
            if not pixmap.isNull():
                # Scale to reasonable size while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(scaled_pixmap)
            else:
                # Fallback to emoji if image not found
                logo_label.setText("🤖")
                logo_label.setStyleSheet("font-size: 60px;")
        except:
            # Fallback to emoji
            logo_label.setText("🤖")
            logo_label.setStyleSheet("font-size: 60px;")
        
        header_layout.addWidget(logo_label)
        
        # Title section
        title_section = QVBoxLayout()
        title_section.setSpacing(5)
        
        title = QLabel("Welcome to SARA")
        title.setObjectName("title")
        
        subtitle = QLabel("Your AI-Powered PC Repair Assistant")
        subtitle.setObjectName("subtitle")
        
        title_section.addWidget(title)
        title_section.addWidget(subtitle)
        
        header_layout.addLayout(title_section)
        header_layout.addStretch()
        
        # AI Status indicator
        self.ai_status_indicator = self._create_status_badge()
        header_layout.addWidget(self.ai_status_indicator)
        
        layout.addLayout(header_layout)

        # ===== SYSTEM HEALTH OVERVIEW =====
        health_label = QLabel("System Health Overview")
        health_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #fff; margin-top: 10px;")
        layout.addWidget(health_label)
        
        health_grid = QGridLayout()
        health_grid.setSpacing(20)
        
        # Create stat cards
        self.cpu_card = self._create_stat_card("🖥️ CPU Usage", "0%", "")
        self.memory_card = self._create_stat_card("💾 Memory", "0%", "")
        self.disk_card = self._create_stat_card("💿 Disk Space", "0%", "")
        self.uptime_card = self._create_stat_card("⏱️ System Uptime", "0h", "")
        
        health_grid.addWidget(self.cpu_card, 0, 0)
        health_grid.addWidget(self.memory_card, 0, 1)
        health_grid.addWidget(self.disk_card, 1, 0)
        health_grid.addWidget(self.uptime_card, 1, 1)
        
        layout.addLayout(health_grid)

        # ===== QUICK ACTIONS =====
        actions_label = QLabel("Quick Actions")
        actions_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #fff; margin-top: 20px;")
        layout.addWidget(actions_label)
        
        actions_grid = QGridLayout()
        actions_grid.setSpacing(15)
        
        # Quick action buttons
        maintenance_btn = self._create_action_button(
            "🔧 Run Maintenance", 
            "Perform full system maintenance",
            self._quick_maintenance
        )
        scan_btn = self._create_action_button(
            "🛡️ Virus Scan", 
            "Check for malware and threats",
            self._quick_scan
        )
        cleanup_btn = self._create_action_button(
            "🧹 Clean Up", 
            "Remove temporary files",
            self._quick_cleanup
        )
        report_btn = self._create_action_button(
            "📊 System Report", 
            "View system health analysis",
            self._quick_report
        )
        
        actions_grid.addWidget(maintenance_btn, 0, 0)
        actions_grid.addWidget(scan_btn, 0, 1)
        actions_grid.addWidget(cleanup_btn, 1, 0)
        actions_grid.addWidget(report_btn, 1, 1)
        
        layout.addLayout(actions_grid)

        # ===== SYSTEM INFORMATION =====
        info_label = QLabel("System Information")
        info_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #fff; margin-top: 20px;")
        layout.addWidget(info_label)
        
        self.system_info_card = self._create_system_info_card()
        layout.addWidget(self.system_info_card)

        layout.addStretch()
        self.setLayout(layout)

    def _create_status_badge(self):
        """Create AI status indicator badge."""
        badge = QFrame()
        badge.setFixedSize(150, 40)
        badge.setStyleSheet("""
            QFrame {
                background: #1b2230;
                border: 1px solid #2b3548;
                border-radius: 20px;
                padding: 5px 15px;
            }
        """)
        
        badge_layout = QHBoxLayout(badge)
        badge_layout.setContentsMargins(10, 5, 10, 5)
        badge_layout.setSpacing(8)
        
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #FFA726; font-size: 18px;")
        
        self.status_text = QLabel("Loading")
        self.status_text.setStyleSheet("color: #e8eef6; font-weight: 600; font-size: 13px;")
        
        badge_layout.addWidget(self.status_dot)
        badge_layout.addWidget(self.status_text)
        badge_layout.addStretch()
        
        return badge

    def _create_stat_card(self, title, value, subtitle):
        """Create a stat card widget."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #1b2230;
                border-radius: 12px;
                border: 1px solid #2b3548;
                padding: 20px;
            }
            QFrame:hover {
                border-color: #6e8bff;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #9eb3ff;")
        
        value_label = QLabel(value)
        value_label.setObjectName("card_value")
        value_label.setStyleSheet("font-size: 32px; font-weight: 700; color: #ffffff;")
        
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet("font-size: 12px; color: #7f8c8d;")
        
        # Progress bar for percentage stats
        progress = QProgressBar()
        progress.setObjectName("card_progress")
        progress.setTextVisible(False)
        progress.setFixedHeight(6)
        progress.setStyleSheet("""
            QProgressBar {
                background: #0f1522;
                border-radius: 3px;
                border: none;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6e8bff, stop:1 #9b6eff);
                border-radius: 3px;
            }
        """)
        progress.setRange(0, 100)
        progress.setValue(0)
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        layout.addWidget(progress)
        layout.addWidget(subtitle_label)
        layout.addStretch()
        
        # Store references for updating
        card.value_label = value_label
        card.subtitle_label = subtitle_label
        card.progress = progress
        
        return card

    def _create_action_button(self, title, description, callback):
        """Create a quick action button."""
        btn = QPushButton()
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(callback)
        
        btn.setStyleSheet("""
            QPushButton {
                background: #1b2230;
                border: 2px solid #2b3548;
                border-radius: 12px;
                padding: 20px;
                text-align: left;
            }
            QPushButton:hover {
                background: #233048;
                border-color: #6e8bff;
            }
            QPushButton:pressed {
                background: #151c29;
            }
        """)
        
        btn_layout = QVBoxLayout()
        btn_layout.setSpacing(5)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #ffffff;")
        
        desc_label = QLabel(description)
        desc_label.setStyleSheet("font-size: 13px; color: #9eb3ff;")
        desc_label.setWordWrap(True)
        
        btn_layout.addWidget(title_label)
        btn_layout.addWidget(desc_label)
        
        btn.setLayout(btn_layout)
        btn.setFixedHeight(90)
        
        return btn

    def _create_system_info_card(self):
        """Create system information card."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #1b2230;
                border-radius: 12px;
                border: 1px solid #2b3548;
                padding: 20px;
            }
        """)
        
        layout = QGridLayout(card)
        layout.setSpacing(15)
        
        # Get system info
        try:
            os_name = f"{platform.system()} {platform.release()}"
            processor = platform.processor() or "Unknown"
            ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
            
            info_items = [
                ("Operating System:", os_name),
                ("Processor:", processor),
                ("Total RAM:", f"{ram_gb} GB"),
                ("Python Version:", platform.python_version()),
            ]
            
            for i, (label, value) in enumerate(info_items):
                label_widget = QLabel(label)
                label_widget.setStyleSheet("font-weight: 600; color: #9eb3ff;")
                
                value_widget = QLabel(value)
                value_widget.setStyleSheet("color: #e8eef6;")
                value_widget.setWordWrap(True)
                
                layout.addWidget(label_widget, i, 0)
                layout.addWidget(value_widget, i, 1)
                
        except Exception as e:
            error_label = QLabel(f"Could not load system info: {e}")
            error_label.setStyleSheet("color: #e74c3c;")
            layout.addWidget(error_label, 0, 0)
        
        return card

    def _update_stats(self):
        """Update dashboard statistics."""
        try:
            # CPU Usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            self.cpu_card.value_label.setText(f"{cpu_percent:.0f}%")
            self.cpu_card.progress.setValue(int(cpu_percent))
            
            # Color code based on usage
            if cpu_percent < 50:
                color = "#4CAF50"  # Green
            elif cpu_percent < 80:
                color = "#FFA726"  # Orange
            else:
                color = "#e74c3c"  # Red
            
            self.cpu_card.subtitle_label.setText(
                f"<span style='color: {color};'>●</span> {self._get_health_text(cpu_percent)}"
            )
            
            # Memory Usage
            memory = psutil.virtual_memory()
            mem_percent = memory.percent
            mem_used = round(memory.used / (1024**3), 1)
            mem_total = round(memory.total / (1024**3), 1)
            
            self.memory_card.value_label.setText(f"{mem_percent:.0f}%")
            self.memory_card.progress.setValue(int(mem_percent))
            self.memory_card.subtitle_label.setText(f"{mem_used} / {mem_total} GB used")
            
            # Disk Space
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            disk_free = round(disk.free / (1024**3), 1)
            
            self.disk_card.value_label.setText(f"{disk_percent:.0f}%")
            self.disk_card.progress.setValue(int(disk_percent))
            self.disk_card.subtitle_label.setText(f"{disk_free} GB free")
            
            # System Uptime
            boot_time = psutil.boot_time()
            uptime_seconds = datetime.now().timestamp() - boot_time
            uptime_hours = int(uptime_seconds / 3600)
            uptime_days = uptime_hours // 24
            uptime_hours_remaining = uptime_hours % 24
            
            if uptime_days > 0:
                uptime_text = f"{uptime_days}d {uptime_hours_remaining}h"
            else:
                uptime_text = f"{uptime_hours}h"
            
            self.uptime_card.value_label.setText(uptime_text)
            self.uptime_card.progress.setValue(0)  # No progress bar for uptime
            self.uptime_card.subtitle_label.setText(
                "Since last restart" if uptime_days < 7 else "⚠️ Consider restarting"
            )
            
            # Update AI status
            if self.ai:
                if getattr(self.ai, 'is_loaded', False):
                    self.status_dot.setStyleSheet("color: #4CAF50; font-size: 18px;")
                    self.status_text.setText("AI Ready")
                elif getattr(self.ai, 'is_loading', False):
                    self.status_dot.setStyleSheet("color: #FFA726; font-size: 18px;")
                    self.status_text.setText("Loading...")
                else:
                    self.status_dot.setStyleSheet("color: #e74c3c; font-size: 18px;")
                    self.status_text.setText("Not Loaded")
            
        except Exception as e:
            print(f"Dashboard update error: {e}")

    def _get_health_text(self, percent):
        """Get health status text based on percentage."""
        if percent < 50:
            return "Healthy"
        elif percent < 80:
            return "Moderate"
        else:
            return "High"

    # ===== QUICK ACTION CALLBACKS =====
    
    def _quick_maintenance(self):
        """Navigate to AI Console and start maintenance."""
        if self.main_window:
            # Switch to AI Console
            self.main_window._switch_page("AI Console")
            
            # Wait a moment for page to load, then send message
            QTimer.singleShot(200, lambda: self._send_ai_message("run maintenance"))

    def _quick_scan(self):
        """Navigate to AI Console and start virus scan."""
        if self.main_window:
            self.main_window._switch_page("AI Console")
            QTimer.singleShot(200, lambda: self._send_ai_message("run virus scan"))

    def _quick_cleanup(self):
        """Navigate to AI Console and start cleanup."""
        if self.main_window:
            self.main_window._switch_page("AI Console")
            QTimer.singleShot(200, lambda: self._send_ai_message("cleanup temp files"))

    def _quick_report(self):
        """Navigate to Reports page."""
        if self.main_window:
            self.main_window._switch_page("Reports")

    def _send_ai_message(self, message):
        """Send a message to AI Console."""
        try:
            # Get the AI Console page
            ai_console = self.main_window._page_instances.get("AI Console")
            if ai_console and hasattr(ai_console, 'input'):
                ai_console.input.setText(message)
                ai_console.send_message()
        except Exception as e:
            print(f"Error sending AI message: {e}")