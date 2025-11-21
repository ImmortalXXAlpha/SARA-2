# ui/reports_page.py
"""
Enhanced Reports Page - Scans Windows Event Logs and generates AI summaries.
"""

import os
import subprocess
import threading
import datetime
import hashlib
import webbrowser
from pathlib import Path
from collections import defaultdict

from PySide6.QtCore import Qt, QTimer, Signal, QThread, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox, QTextEdit,
    QTabWidget, QProgressBar, QFrame, QComboBox, QSplitter
)

# Reports directory
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


class EventLogScanner(QThread):
    """Background thread to scan Windows Event Logs."""
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(list)  # List of error dicts
    
    def __init__(self, log_name="System", hours=24, max_events=200):
        super().__init__()
        self.log_name = log_name
        self.hours = hours
        self.max_events = max_events
    
    def run(self):
        try:
            self.status.emit(f"Scanning {self.log_name} log...")
            self.progress.emit(10)
            
            # PowerShell command to get recent errors/warnings
            time_filter = f"(Get-Date).AddHours(-{self.hours})"
            ps_cmd = f'''
            $events = Get-WinEvent -LogName {self.log_name} -MaxEvents {self.max_events} -ErrorAction SilentlyContinue | 
                Where-Object {{ ($_.Level -le 3) -and ($_.TimeCreated -gt {time_filter}) }} |
                Select-Object TimeCreated, Id, LevelDisplayName, ProviderName, Message |
                ForEach-Object {{
                    [PSCustomObject]@{{
                        Time = $_.TimeCreated.ToString("yyyy-MM-dd HH:mm:ss")
                        Id = $_.Id
                        Level = $_.LevelDisplayName
                        Source = $_.ProviderName
                        Message = ($_.Message -replace "`r`n", " " -replace "`n", " ").Substring(0, [Math]::Min(500, $_.Message.Length))
                    }}
                }}
            $events | ConvertTo-Json -Compress
            '''
            
            self.progress.emit(30)
            
            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            )
            
            self.progress.emit(70)
            
            events = []
            if result.stdout.strip():
                import json
                try:
                    data = json.loads(result.stdout)
                    # Handle single event (not array)
                    if isinstance(data, dict):
                        data = [data]
                    events = data if isinstance(data, list) else []
                except json.JSONDecodeError:
                    pass
            
            self.progress.emit(100)
            self.status.emit(f"Found {len(events)} events")
            self.finished.emit(events)
            
        except subprocess.TimeoutExpired:
            self.status.emit("Scan timed out")
            self.finished.emit([])
        except Exception as e:
            self.status.emit(f"Error: {e}")
            self.finished.emit([])


class AIReportGenerator(QThread):
    """Background thread to generate AI summary of errors."""
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(str)  # The generated report
    
    def __init__(self, ai, errors):
        super().__init__()
        self.ai = ai
        self.errors = errors
    
    def run(self):
        if not self.ai or not getattr(self.ai, 'is_loaded', False):
            self.finished.emit("")
            return
        
        if not self.errors:
            self.finished.emit("No errors found in the scanned time period.")
            return
        
        try:
            self.status.emit("Generating AI summary...")
            self.progress.emit(20)
            
            # Build a summary of errors for the AI
            error_summary = []
            for i, err in enumerate(self.errors[:15]):  # Limit to 15 for context
                error_summary.append(
                    f"{i+1}. [{err.get('Level', 'Error')}] {err.get('Source', 'Unknown')}: "
                    f"{err.get('Message', 'No message')[:200]}"
                )
            
            errors_text = "\n".join(error_summary)
            
            prompt = f"""You are a helpful PC technician assistant. Analyze these Windows Event Log errors and provide a brief, easy-to-understand summary for a non-technical user.

For each significant issue:
1. Explain what it means in simple terms
2. Whether it's serious or can be ignored
3. Any recommended action

Keep your response concise and friendly. Group similar errors together.

ERRORS FROM EVENT LOG:
{errors_text}

Provide your analysis:"""

            self.progress.emit(50)
            
            response = self.ai.generate(prompt, max_new_tokens=512, temperature=0.5)
            
            self.progress.emit(100)
            self.status.emit("Report generated")
            self.finished.emit(response)
            
        except Exception as e:
            self.status.emit(f"AI error: {e}")
            self.finished.emit(f"Could not generate AI summary: {e}")


class ReportsPage(QWidget):
    """Reports page with Windows Event Log scanning and AI analysis."""
    
    def __init__(self, ai=None):
        super().__init__()
        self.ai = ai
        self.current_events = []
        self.scanner = None
        self.ai_generator = None
        
        self._init_ui()
    
    def set_ai(self, ai):
        """Set AI instance (called from main_window)."""
        self.ai = ai
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header
        title = QLabel("📜 System Reports")
        title.setObjectName("title")
        subtitle = QLabel("Scan Windows Event Logs and get AI-powered analysis")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_scan_tab(), "🔍 Event Log Scanner")
        self.tabs.addTab(self._create_saved_tab(), "📁 Saved Reports")
        layout.addWidget(self.tabs)

    def _create_scan_tab(self):
        """Create the event log scanning tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # Controls row
        controls = QHBoxLayout()
        
        controls.addWidget(QLabel("Log:"))
        self.log_combo = QComboBox()
        self.log_combo.addItems(["System", "Application", "Security"])
        self.log_combo.setCurrentIndex(0)
        controls.addWidget(self.log_combo)
        
        controls.addWidget(QLabel("Time range:"))
        self.time_combo = QComboBox()
        self.time_combo.addItems(["Last 24 hours", "Last 7 days", "Last 30 days"])
        controls.addWidget(self.time_combo)
        
        controls.addStretch()
        
        self.scan_btn = QPushButton("🔍 Scan Event Logs")
        self.scan_btn.setStyleSheet("""
            QPushButton {
                background: #6e8bff;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 10px 20px;
                font-weight: 600;
            }
            QPushButton:hover { background: #869eff; }
            QPushButton:disabled { background: #3d4a6b; }
        """)
        self.scan_btn.clicked.connect(self._start_scan)
        controls.addWidget(self.scan_btn)
        
        layout.addLayout(controls)

        # Progress
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #9eb3ff; font-style: italic;")
        layout.addWidget(self.status_label)

        # Splitter for results
        splitter = QSplitter(Qt.Vertical)
        
        # AI Summary section
        ai_frame = QFrame()
        ai_frame.setStyleSheet("QFrame { background: #1b2230; border-radius: 8px; }")
        ai_layout = QVBoxLayout(ai_frame)
        ai_layout.setContentsMargins(15, 15, 15, 15)
        
        ai_header = QHBoxLayout()
        ai_header.addWidget(QLabel("🤖 AI Analysis"))
        self.regenerate_btn = QPushButton("Regenerate")
        self.regenerate_btn.setEnabled(False)
        self.regenerate_btn.clicked.connect(self._generate_ai_report)
        ai_header.addStretch()
        ai_header.addWidget(self.regenerate_btn)
        ai_layout.addLayout(ai_header)
        
        self.ai_summary = QTextEdit()
        self.ai_summary.setReadOnly(True)
        self.ai_summary.setPlaceholderText("AI analysis will appear here after scanning...")
        self.ai_summary.setStyleSheet("""
            QTextEdit {
                background: #0f1522;
                border: 1px solid #2b3548;
                border-radius: 6px;
                padding: 10px;
                color: #e8eef6;
            }
        """)
        self.ai_summary.setMinimumHeight(150)
        ai_layout.addWidget(self.ai_summary)
        splitter.addWidget(ai_frame)

        # Raw errors section
        raw_frame = QFrame()
        raw_frame.setStyleSheet("QFrame { background: #1b2230; border-radius: 8px; }")
        raw_layout = QVBoxLayout(raw_frame)
        raw_layout.setContentsMargins(15, 15, 15, 15)
        
        raw_header = QHBoxLayout()
        raw_header.addWidget(QLabel("📋 Raw Event Log Errors"))
        self.error_count_label = QLabel("")
        self.error_count_label.setStyleSheet("color: #9eb3ff;")
        raw_header.addStretch()
        raw_header.addWidget(self.error_count_label)
        raw_layout.addLayout(raw_header)
        
        self.raw_errors = QTextEdit()
        self.raw_errors.setReadOnly(True)
        self.raw_errors.setPlaceholderText("Raw errors will appear here...")
        self.raw_errors.setStyleSheet("""
            QTextEdit {
                background: #0f1522;
                border: 1px solid #2b3548;
                border-radius: 6px;
                padding: 10px;
                color: #e8eef6;
                font-family: 'Consolas', monospace;
                font-size: 12px;
            }
        """)
        raw_layout.addWidget(self.raw_errors)
        splitter.addWidget(raw_frame)

        layout.addWidget(splitter, 1)

        # Save button
        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        self.save_btn = QPushButton("💾 Save Report")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_report)
        bottom_row.addWidget(self.save_btn)
        layout.addLayout(bottom_row)

        return widget

    def _create_saved_tab(self):
        """Create the saved reports tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        # List of saved reports
        self.report_list = QListWidget()
        self.report_list.setStyleSheet("""
            QListWidget {
                background: #121826;
                border: 1px solid #2b3548;
                border-radius: 8px;
                color: #e8eef6;
                padding: 6px;
            }
            QListWidget::item:selected {
                background: #6e8bff;
                color: white;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #2b3548;
            }
        """)
        self.report_list.itemDoubleClicked.connect(self._open_report)
        layout.addWidget(self.report_list)

        # Buttons
        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self._refresh_reports)
        self.open_btn = QPushButton("📂 Open Selected")
        self.open_btn.clicked.connect(self._open_report)
        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self._delete_report)
        
        for btn in (self.refresh_btn, self.open_btn, self.delete_btn):
            btn.setStyleSheet("""
                QPushButton {
                    background: #1b2230;
                    color: #e8eef6;
                    border: 1px solid #2b3548;
                    border-radius: 6px;
                    padding: 8px 16px;
                }
                QPushButton:hover { background: #2b3548; border-color: #6e8bff; }
            """)
        
        btn_row.addWidget(self.refresh_btn)
        btn_row.addWidget(self.open_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.delete_btn)
        layout.addLayout(btn_row)

        # Auto-refresh
        self._refresh_reports()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_reports)
        self.refresh_timer.start(30000)

        return widget

    # ---- Scanning ----
    def _start_scan(self):
        if self.scanner and self.scanner.isRunning():
            return
        
        log_name = self.log_combo.currentText()
        hours = {0: 24, 1: 168, 2: 720}[self.time_combo.currentIndex()]
        
        self.scan_btn.setEnabled(False)
        self.progress.show()
        self.progress.setValue(0)
        self.status_label.setText("Starting scan...")
        self.ai_summary.clear()
        self.raw_errors.clear()
        
        self.scanner = EventLogScanner(log_name, hours)
        self.scanner.progress.connect(self.progress.setValue)
        self.scanner.status.connect(self.status_label.setText)
        self.scanner.finished.connect(self._on_scan_finished)
        self.scanner.start()

    @Slot(list)
    def _on_scan_finished(self, events):
        self.scan_btn.setEnabled(True)
        self.current_events = events
        
        # Deduplicate by message hash
        seen = set()
        unique_events = []
        for ev in events:
            msg_hash = hashlib.md5(
                f"{ev.get('Source', '')}{ev.get('Id', '')}{ev.get('Message', '')[:100]}".encode()
            ).hexdigest()
            if msg_hash not in seen:
                seen.add(msg_hash)
                unique_events.append(ev)
        
        self.current_events = unique_events
        self.error_count_label.setText(f"{len(unique_events)} unique errors (from {len(events)} total)")
        
        # Display raw errors
        if unique_events:
            raw_text = []
            for ev in unique_events:
                raw_text.append(
                    f"[{ev.get('Time', 'Unknown')}] {ev.get('Level', 'Error')} - {ev.get('Source', 'Unknown')}\n"
                    f"  Event ID: {ev.get('Id', 'N/A')}\n"
                    f"  {ev.get('Message', 'No message')}\n"
                )
            self.raw_errors.setPlainText("\n".join(raw_text))
            self.save_btn.setEnabled(True)
            self.regenerate_btn.setEnabled(True)
            
            # Auto-generate AI report
            self._generate_ai_report()
        else:
            self.raw_errors.setPlainText("No errors or warnings found in the selected time range.")
            self.ai_summary.setPlainText("✅ No issues found! Your system looks healthy.")
            self.progress.hide()

    def _generate_ai_report(self):
        if not self.current_events:
            return
        
        if not self.ai or not getattr(self.ai, 'is_loaded', False):
            self.ai_summary.setPlainText(
                "⚠️ AI model not loaded. Please load a model in the AI Console to generate summaries.\n\n"
                "You can still view the raw errors below."
            )
            self.progress.hide()
            return
        
        self.ai_summary.setPlainText("Generating AI analysis...")
        self.regenerate_btn.setEnabled(False)
        self.progress.show()
        self.progress.setValue(0)
        
        self.ai_generator = AIReportGenerator(self.ai, self.current_events)
        self.ai_generator.progress.connect(self.progress.setValue)
        self.ai_generator.status.connect(self.status_label.setText)
        self.ai_generator.finished.connect(self._on_ai_finished)
        self.ai_generator.start()

    @Slot(str)
    def _on_ai_finished(self, report):
        self.ai_summary.setPlainText(report)
        self.regenerate_btn.setEnabled(True)
        self.progress.hide()
        self.status_label.setText("Analysis complete")

    # ---- Save/Load ----
    def _save_report(self):
        if not self.current_events:
            return
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_name = self.log_combo.currentText()
        filename = REPORTS_DIR / f"report_{log_name}_{timestamp}.txt"
        
        try:
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"SARA System Report - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Log: {log_name} | Time range: {self.time_combo.currentText()}\n")
                f.write("=" * 60 + "\n\n")
                
                f.write("=== AI ANALYSIS ===\n\n")
                f.write(self.ai_summary.toPlainText() or "No AI analysis generated")
                f.write("\n\n")
                
                f.write("=== RAW EVENT LOG ERRORS ===\n\n")
                f.write(self.raw_errors.toPlainText())
            
            QMessageBox.information(self, "Saved", f"Report saved to:\n{filename}")
            self._refresh_reports()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save report:\n{e}")

    def _refresh_reports(self):
        self.report_list.clear()
        
        if not REPORTS_DIR.exists():
            REPORTS_DIR.mkdir(exist_ok=True)
        
        files = sorted(REPORTS_DIR.glob("*.txt"), key=os.path.getmtime, reverse=True)
        
        if not files:
            item = QListWidgetItem("No saved reports yet")
            item.setFlags(Qt.NoItemFlags)
            self.report_list.addItem(item)
            return
        
        for f in files:
            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
            size_kb = f.stat().st_size / 1024
            label = f"{f.stem}  |  {mtime.strftime('%Y-%m-%d %H:%M')}  |  {size_kb:.1f} KB"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, str(f))
            self.report_list.addItem(item)

    def _open_report(self, item=None):
        if item is None:
            item = self.report_list.currentItem()
        if not item or not item.data(Qt.UserRole):
            return
        
        path = item.data(Qt.UserRole)
        if os.path.exists(path):
            try:
                webbrowser.open(path)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not open file:\n{e}")

    def _delete_report(self):
        item = self.report_list.currentItem()
        if not item or not item.data(Qt.UserRole):
            return
        
        path = item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, "Delete Report",
            f"Delete this report?\n{os.path.basename(path)}",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                os.remove(path)
                self._refresh_reports()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete:\n{e}")