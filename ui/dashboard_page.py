# ui/dashboard_page.py
"""
Improved Dashboard - System overview with useful information display.
"""

import psutil
import platform
import os
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QFrame, QHBoxLayout, 
    QGridLayout, QPushButton, QProgressBar, QScrollArea
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
        # Main layout for the page
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #1b2230;
                width: 12px;
                border-radius: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #3d4a6b;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #6e8bff;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar:horizontal {
                height: 0;
            }
        """)
        
        # Content widget inside scroll area
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(25)

        # ===== HEADER WITH LOGO =====
        header_layout = QHBoxLayout()
        
        # SARA Logo
        logo_label = QLabel()
        try:
            pixmap = QPixmap("assets/SARA.png")
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(scaled_pixmap)
            else:
                logo_label.setText("🤖")
                logo_label.setStyleSheet("font-size: 60px;")
        except:
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

        # ===== AI STATUS =====
        ai_label = QLabel("AI Status")
        ai_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #fff; margin-top: 20px;")
        layout.addWidget(ai_label)
        
        self.ai_status_card = self._create_ai_status_card()
        layout.addWidget(self.ai_status_card)

        # ===== RECENT ACTIVITY =====
        activity_label = QLabel("Recent Activity")
        activity_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #fff; margin-top: 20px;")
        layout.addWidget(activity_label)
        
        self.activity_card = self._create_activity_card()
        layout.addWidget(self.activity_card)

        # ===== LAST REPORT =====
        report_label = QLabel("Latest System Report")
        report_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #fff; margin-top: 20px;")
        layout.addWidget(report_label)
        
        self.last_report_card = self._create_last_report_card()
        layout.addWidget(self.last_report_card)

        # ===== SYSTEM INFORMATION =====
        info_label = QLabel("System Information")
        info_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #fff; margin-top: 20px;")
        layout.addWidget(info_label)
        
        self.system_info_card = self._create_system_info_card()
        layout.addWidget(self.system_info_card)

        layout.addStretch()
        
        # Set content widget to scroll area
        scroll_area.setWidget(content_widget)
        
        # Add scroll area to main layout
        main_layout.addWidget(scroll_area)

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

    def _create_ai_status_card(self):
        """Create AI status card."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #1b2230;
                border-radius: 12px;
                border: 1px solid #2b3548;
                padding: 20px;
            }
        """)
        
        layout = QHBoxLayout(card)
        layout.setSpacing(20)
        
        # Status indicator
        self.ai_status_dot = QLabel("●")
        self.ai_status_dot.setStyleSheet("color: #FFA726; font-size: 36px;")
        layout.addWidget(self.ai_status_dot)
        
        # Status info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(5)
        
        self.ai_status_text = QLabel("AI Model Loading...")
        self.ai_status_text.setStyleSheet("font-size: 16px; font-weight: 600; color: #ffffff;")
        
        self.ai_model_text = QLabel("Model: Loading...")
        self.ai_model_text.setStyleSheet("font-size: 13px; color: #9eb3ff;")
        
        self.ai_speed_text = QLabel("Speed: --")
        self.ai_speed_text.setStyleSheet("font-size: 13px; color: #9eb3ff;")
        
        info_layout.addWidget(self.ai_status_text)
        info_layout.addWidget(self.ai_model_text)
        info_layout.addWidget(self.ai_speed_text)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        return card

    def _create_activity_card(self):
        """Create recent activity card."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #1b2230;
                border-radius: 12px;
                border: 1px solid #2b3548;
                padding: 20px;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        
        self.activity_label = QLabel("No recent maintenance activity")
        self.activity_label.setStyleSheet("color: #7f8c8d; font-size: 14px;")
        self.activity_label.setWordWrap(True)
        
        layout.addWidget(self.activity_label)
        
        return card

    def _create_last_report_card(self):
        """Create last report summary card."""
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background: #1b2230;
                border-radius: 12px;
                border: 1px solid #2b3548;
                padding: 20px;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(15)
        
        # Check for latest report
        reports_dir = Path(__file__).resolve().parent.parent / "reports"
        
        if reports_dir.exists():
            # Get most recent report file
            reports = list(reports_dir.glob("*.txt")) + list(reports_dir.glob("*.pdf"))
            if reports:
                latest_report = max(reports, key=os.path.getmtime)
                file_time = datetime.fromtimestamp(latest_report.stat().st_mtime)
                time_ago = self._time_ago(file_time)
                
                # Report found
                header = QLabel(f"📄 {latest_report.stem}")
                header.setStyleSheet("font-size: 15px; font-weight: 600; color: #ffffff;")
                
                time_label = QLabel(f"Generated {time_ago}")
                time_label.setStyleSheet("font-size: 13px; color: #9eb3ff;")
                
                # View button
                view_btn = QPushButton("📊 View Reports")
                view_btn.setCursor(Qt.PointingHandCursor)
                view_btn.setStyleSheet("""
                    QPushButton {
                        background: #6e8bff;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 10px 20px;
                        font-weight: 600;
                    }
                    QPushButton:hover {
                        background: #869eff;
                    }
                """)
                view_btn.clicked.connect(self._open_reports_page)
                
                layout.addWidget(header)
                layout.addWidget(time_label)
                layout.addWidget(view_btn)
            else:
                # No reports yet
                no_reports = QLabel("📭 No reports generated yet")
                no_reports.setStyleSheet("color: #7f8c8d; font-size: 14px;")
                
                hint = QLabel("Generate a report from the Reports page to see system health analysis")
                hint.setStyleSheet("color: #7f8c8d; font-size: 12px;")
                hint.setWordWrap(True)
                
                layout.addWidget(no_reports)
                layout.addWidget(hint)
        else:
            # Reports directory doesn't exist
            no_reports = QLabel("📭 No reports directory found")
            no_reports.setStyleSheet("color: #7f8c8d; font-size: 14px;")
            layout.addWidget(no_reports)
        
        return card

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
                    self.ai_status_dot.setStyleSheet("color: #4CAF50; font-size: 36px;")
                    self.ai_status_text.setText("AI Ready")
                    
                    model_name = getattr(self.ai, 'model_key', 'Unknown')
                    self.ai_model_text.setText(f"Model: {model_name}")
                    
                    # Get benchmark if available
                    if hasattr(self.ai, '_last_benchmark'):
                        speed = getattr(self.ai, '_last_benchmark', 0)
                        self.ai_speed_text.setText(f"Speed: {speed:.1f} tokens/sec")
                    else:
                        self.ai_speed_text.setText("Speed: Ready")
                        
                elif getattr(self.ai, 'is_loading', False):
                    self.ai_status_dot.setStyleSheet("color: #FFA726; font-size: 36px;")
                    self.ai_status_text.setText("Loading Model...")
                    self.ai_model_text.setText("Please wait...")
                    self.ai_speed_text.setText("")
                else:
                    self.ai_status_dot.setStyleSheet("color: #e74c3c; font-size: 36px;")
                    self.ai_status_text.setText("AI Not Loaded")
                    self.ai_model_text.setText("Go to AI Console to load")
                    self.ai_speed_text.setText("")
            
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

    def _time_ago(self, dt):
        """Get human-readable time ago string."""
        now = datetime.now()
        diff = now - dt
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        else:
            days = int(seconds / 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"

    def _open_reports_page(self):
        """Navigate to Reports page."""
        if self.main_window:
            self.main_window._switch_page("Reports")