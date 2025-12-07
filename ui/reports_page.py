# ui/reports_page.py
"""
Enhanced Reports Page - Scans Windows Event Logs and generates AI summaries.
Features: Multiple log sources, detailed AI analysis, PDF/TXT export.
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
    QTabWidget, QProgressBar, QFrame, QComboBox, QSplitter,
    QCheckBox, QGroupBox, QGridLayout, QFileDialog
)

# Reports directory
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

# Available Windows Event Logs
EVENT_LOGS = {
    "System": "Core Windows system events, drivers, services",
    "Application": "Application errors, crashes, software issues", 
    "Security": "Login attempts, permission changes, security events",
    "Setup": "Windows Update and installation events",
    "Windows PowerShell": "PowerShell execution and script errors",
}

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


class EventLogScanner(QThread):
    """Background thread to scan Windows Event Logs."""
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(list, str)  # List of error dicts, log name
    
    def __init__(self, log_names, hours=24, max_events=300, levels=None):
        super().__init__()
        self.log_names = log_names if isinstance(log_names, list) else [log_names]
        self.hours = hours
        self.max_events = max_events
        self.levels = levels or [1, 2, 3]  # 1=Critical, 2=Error, 3=Warning
    
    def run(self):
        all_events = []
        total_logs = len(self.log_names)
        
        for idx, log_name in enumerate(self.log_names):
            try:
                base_progress = int((idx / total_logs) * 80)
                self.status.emit(f"Scanning {log_name} log ({idx+1}/{total_logs})...")
                self.progress.emit(base_progress + 5)
                
                # Build level filter
                level_filter = " -or ".join([f"$_.Level -eq {l}" for l in self.levels])
                time_filter = f"(Get-Date).AddHours(-{self.hours})"
                
                ps_cmd = f'''
                try {{
                    $events = Get-WinEvent -LogName "{log_name}" -MaxEvents {self.max_events} -ErrorAction SilentlyContinue | 
                        Where-Object {{ ({level_filter}) -and ($_.TimeCreated -gt {time_filter}) }} |
                        Select-Object TimeCreated, Id, Level, LevelDisplayName, ProviderName, Message |
                        ForEach-Object {{
                            $msg = if ($_.Message) {{ $_.Message -replace "`r`n", " " -replace "`n", " " }} else {{ "No message" }}
                            $msg = $msg.Substring(0, [Math]::Min(600, $msg.Length))
                            [PSCustomObject]@{{
                                Time = $_.TimeCreated.ToString("yyyy-MM-dd HH:mm:ss")
                                Id = $_.Id
                                Level = $_.Level
                                LevelName = $_.LevelDisplayName
                                Source = $_.ProviderName
                                Log = "{log_name}"
                                Message = $msg
                            }}
                        }}
                    $events | ConvertTo-Json -Compress
                }} catch {{
                    Write-Output "[]"
                }}
                '''
                
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                    capture_output=True,
                    text=True,
                    timeout=45,
                    creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
                )
                
                if result.stdout.strip() and result.stdout.strip() != "[]":
                    import json
                    try:
                        data = json.loads(result.stdout)
                        if isinstance(data, dict):
                            data = [data]
                        if isinstance(data, list):
                            all_events.extend(data)
                    except json.JSONDecodeError:
                        pass
                        
            except subprocess.TimeoutExpired:
                self.status.emit(f"Timeout scanning {log_name}")
            except Exception as e:
                self.status.emit(f"Error scanning {log_name}: {e}")
        
        self.progress.emit(90)
        self.status.emit(f"Found {len(all_events)} total events")
        
        # Sort by time (newest first)
        all_events.sort(key=lambda x: x.get('Time', ''), reverse=True)
        
        self.progress.emit(100)
        log_str = ", ".join(self.log_names)
        self.finished.emit(all_events, log_str)


class AIReportGenerator(QThread):
    """Background thread to generate detailed AI summary of errors."""
    progress = Signal(int)
    status = Signal(str)
    finished = Signal(str)
    
    def __init__(self, ai, errors, scan_info=""):
        super().__init__()
        self.ai = ai
        self.errors = errors
        self.scan_info = scan_info
    
    def run(self):
        if not self.ai or not getattr(self.ai, 'is_loaded', False):
            self.finished.emit("")
            return
        
        if not self.errors:
            self.finished.emit("✅ No errors or warnings found! Your system appears to be running smoothly.")
            return
        
        try:
            self.status.emit("Analyzing errors with AI...")
            self.progress.emit(10)
            
            # Categorize errors
            critical = [e for e in self.errors if e.get('Level') == 1]
            errors = [e for e in self.errors if e.get('Level') == 2]
            warnings = [e for e in self.errors if e.get('Level') == 3]
            
            # Build detailed summary for AI
            summary_parts = []
            
            if critical:
                summary_parts.append("CRITICAL ERRORS (Most Severe):")
                for e in critical[:5]:
                    summary_parts.append(f"  - [{e.get('Log')}] {e.get('Source')}: {e.get('Message', '')[:250]}")
            
            if errors:
                summary_parts.append("\nERRORS:")
                for e in errors[:10]:
                    summary_parts.append(f"  - [{e.get('Log')}] {e.get('Source')}: {e.get('Message', '')[:250]}")
            
            if warnings:
                summary_parts.append("\nWARNINGS:")
                for e in warnings[:10]:
                    summary_parts.append(f"  - [{e.get('Log')}] {e.get('Source')}: {e.get('Message', '')[:200]}")
            
            errors_text = "\n".join(summary_parts)
            
            self.progress.emit(30)
            
            prompt = f"""You are an expert Windows PC technician helping a non-technical user understand their computer's health.

SCAN INFORMATION:
{self.scan_info}
Total events found: {len(self.errors)} ({len(critical)} critical, {len(errors)} errors, {len(warnings)} warnings)

EVENT LOG ENTRIES:
{errors_text}

Please provide a comprehensive but easy-to-understand analysis with the following sections:

## 🔴 Critical Issues (if any)
Explain any critical errors that need immediate attention. What could happen if ignored?

## 🟠 Errors to Address
Explain significant errors. Are they one-time glitches or recurring problems?

## 🟡 Warnings & Minor Issues  
Briefly mention warnings that are usually safe to ignore vs ones to watch.

## 💡 Recommendations
Provide 2-4 specific, actionable steps the user can take to fix or investigate the issues. Include:
- Any Windows tools they can run (like sfc /scannow, chkdsk, etc.)
- Settings to check
- Whether professional help might be needed

## 📊 Overall Health Assessment
Give a simple verdict: Is this PC healthy, needs attention, or has serious problems?

Keep explanations simple - avoid technical jargon. Use analogies if helpful."""

            self.progress.emit(50)
            
            response = self.ai.generate(prompt, max_new_tokens=800, temperature=0.4)
            
            self.progress.emit(100)
            self.status.emit("Analysis complete")
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
        self.current_scan_info = ""
        self.scanner = None
        self.ai_generator = None
        
        self._init_ui()
    
    def set_ai(self, ai):
        self.ai = ai
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # Header
        title = QLabel("📜 System Health Reports")
        title.setObjectName("title")
        subtitle = QLabel("Scan Windows Event Logs for errors and get AI-powered diagnosis")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_scan_tab(), "🔍 Scan & Analyze")
        self.tabs.addTab(self._create_saved_tab(), "📁 Saved Reports")
        layout.addWidget(self.tabs)

    def _create_scan_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(15)

        # Scan options group
        options_group = QGroupBox("Scan Options")
        options_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #2b3548;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
            }
        """)
        options_layout = QVBoxLayout(options_group)
        
        # Log selection
        log_row = QHBoxLayout()
        log_row.addWidget(QLabel("Event Logs to Scan:"))
        log_row.addStretch()
        
        self.log_checks = {}
        for log_name, description in EVENT_LOGS.items():
            cb = QCheckBox(log_name)
            cb.setToolTip(description)
            cb.setChecked(log_name in ["System", "Application"])
            self.log_checks[log_name] = cb
            log_row.addWidget(cb)
        
        # Select All button
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setFixedWidth(80)
        self.select_all_btn.clicked.connect(self._toggle_all_logs)
        log_row.addWidget(self.select_all_btn)
        options_layout.addLayout(log_row)
        
        # Severity and time row
        filter_row = QHBoxLayout()
        
        filter_row.addWidget(QLabel("Severity:"))
        self.severity_combo = QComboBox()
        self.severity_combo.addItems([
            "Critical & Errors Only",
            "Errors & Warnings", 
            "All (Critical, Errors, Warnings)"
        ])
        self.severity_combo.setCurrentIndex(2)
        filter_row.addWidget(self.severity_combo)
        
        filter_row.addSpacing(20)
        
        filter_row.addWidget(QLabel("Time Range:"))
        self.time_combo = QComboBox()
        self.time_combo.addItems([
            "Last 6 hours",
            "Last 24 hours", 
            "Last 3 days",
            "Last 7 days", 
            "Last 30 days"
        ])
        self.time_combo.setCurrentIndex(1)
        filter_row.addWidget(self.time_combo)
        
        filter_row.addStretch()
        options_layout.addLayout(filter_row)
        
        layout.addWidget(options_group)

        # Scan button row
        scan_row = QHBoxLayout()
        self.scan_btn = QPushButton("🔍 Start Scan")
        self.scan_btn.setStyleSheet("""
            QPushButton {
                background: #6e8bff;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 30px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover { background: #869eff; }
            QPushButton:disabled { background: #3d4a6b; }
        """)
        self.scan_btn.clicked.connect(self._start_scan)
        scan_row.addWidget(self.scan_btn)
        
        self.quick_scan_btn = QPushButton("⚡ Quick Scan (System Only)")
        self.quick_scan_btn.setStyleSheet("""
            QPushButton {
                background: #1b2230;
                color: #e8eef6;
                border: 1px solid #2b3548;
                border-radius: 8px;
                padding: 12px 20px;
                font-weight: 500;
            }
            QPushButton:hover { background: #2b3548; }
        """)
        self.quick_scan_btn.clicked.connect(self._quick_scan)
        scan_row.addWidget(self.quick_scan_btn)
        
        scan_row.addStretch()
        layout.addLayout(scan_row)

        # Progress
        progress_row = QHBoxLayout()
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFixedHeight(8)
        self.progress.hide()
        progress_row.addWidget(self.progress)
        
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #9eb3ff; font-style: italic;")
        self.status_label.setFixedWidth(200)
        progress_row.addWidget(self.status_label)
        layout.addLayout(progress_row)

        # Results splitter
        splitter = QSplitter(Qt.Vertical)
        
        # AI Summary section
        ai_frame = QFrame()
        ai_frame.setStyleSheet("QFrame { background: #1b2230; border-radius: 10px; }")
        ai_layout = QVBoxLayout(ai_frame)
        ai_layout.setContentsMargins(15, 15, 15, 15)
        
        ai_header = QHBoxLayout()
        ai_title = QLabel("🤖 AI Health Analysis")
        ai_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        ai_header.addWidget(ai_title)
        ai_header.addStretch()
        
        self.regenerate_btn = QPushButton("🔄 Regenerate")
        self.regenerate_btn.setEnabled(False)
        self.regenerate_btn.clicked.connect(self._generate_ai_report)
        ai_header.addWidget(self.regenerate_btn)
        ai_layout.addLayout(ai_header)
        
        self.ai_summary = QTextEdit()
        self.ai_summary.setReadOnly(True)
        self.ai_summary.setPlaceholderText("AI analysis will appear here after scanning...\n\nThe AI will explain any issues in plain English and provide recommendations.")
        self.ai_summary.setStyleSheet("""
            QTextEdit {
                background: #0f1522;
                border: 1px solid #2b3548;
                border-radius: 8px;
                padding: 12px;
                color: #e8eef6;
                font-size: 13px;
                line-height: 1.5;
            }
        """)
        self.ai_summary.setMinimumHeight(200)
        ai_layout.addWidget(self.ai_summary)
        splitter.addWidget(ai_frame)

        # Raw errors section
        raw_frame = QFrame()
        raw_frame.setStyleSheet("QFrame { background: #1b2230; border-radius: 10px; }")
        raw_layout = QVBoxLayout(raw_frame)
        raw_layout.setContentsMargins(15, 15, 15, 15)
        
        raw_header = QHBoxLayout()
        raw_title = QLabel("📋 Raw Event Log Entries")
        raw_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        raw_header.addWidget(raw_title)
        
        self.error_count_label = QLabel("")
        self.error_count_label.setStyleSheet("color: #9eb3ff;")
        raw_header.addStretch()
        raw_header.addWidget(self.error_count_label)
        raw_layout.addLayout(raw_header)
        
        self.raw_errors = QTextEdit()
        self.raw_errors.setReadOnly(True)
        self.raw_errors.setPlaceholderText("Raw event log entries will appear here...")
        self.raw_errors.setStyleSheet("""
            QTextEdit {
                background: #0f1522;
                border: 1px solid #2b3548;
                border-radius: 8px;
                padding: 10px;
                color: #c8d0e8;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        raw_layout.addWidget(self.raw_errors)
        splitter.addWidget(raw_frame)
        
        splitter.setSizes([350, 250])
        layout.addWidget(splitter, 1)

        # Export buttons
        export_row = QHBoxLayout()
        export_row.addStretch()
        
        self.save_txt_btn = QPushButton("💾 Save as TXT")
        self.save_txt_btn.setEnabled(False)
        self.save_txt_btn.clicked.connect(lambda: self._save_report("txt"))
        
        self.save_pdf_btn = QPushButton("📄 Export as PDF")
        self.save_pdf_btn.setEnabled(False)
        self.save_pdf_btn.clicked.connect(lambda: self._save_report("pdf"))
        
        for btn in (self.save_txt_btn, self.save_pdf_btn):
            btn.setStyleSheet("""
                QPushButton {
                    background: #1b2230;
                    color: #e8eef6;
                    border: 1px solid #2b3548;
                    border-radius: 6px;
                    padding: 8px 16px;
                }
                QPushButton:hover { background: #2b3548; border-color: #6e8bff; }
                QPushButton:disabled { color: #555; }
            """)
        
        export_row.addWidget(self.save_txt_btn)
        export_row.addWidget(self.save_pdf_btn)
        layout.addLayout(export_row)

        return widget

    def _create_saved_tab(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 15, 10, 10)
        layout.setSpacing(15)

        self.report_list = QListWidget()
        self.report_list.setStyleSheet("""
            QListWidget {
                background: #121826;
                border: 1px solid #2b3548;
                border-radius: 8px;
                color: #e8eef6;
                padding: 8px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #2b3548;
                border-radius: 4px;
            }
            QListWidget::item:selected {
                background: #6e8bff;
                color: white;
            }
            QListWidget::item:hover {
                background: #1b2230;
            }
        """)
        self.report_list.itemDoubleClicked.connect(self._open_report)
        layout.addWidget(self.report_list)

        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.clicked.connect(self._refresh_reports)
        self.open_btn = QPushButton("📂 Open")
        self.open_btn.clicked.connect(self._open_report)
        self.open_folder_btn = QPushButton("📁 Open Folder")
        self.open_folder_btn.clicked.connect(self._open_reports_folder)
        self.delete_btn = QPushButton("🗑️ Delete")
        self.delete_btn.clicked.connect(self._delete_report)
        
        for btn in (self.refresh_btn, self.open_btn, self.open_folder_btn, self.delete_btn):
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
        btn_row.addWidget(self.open_folder_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.delete_btn)
        layout.addLayout(btn_row)

        self._refresh_reports()
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_reports)
        self.refresh_timer.start(30000)

        return widget

    # ---- Scanning ----
    def _toggle_all_logs(self):
        all_checked = all(cb.isChecked() for cb in self.log_checks.values())
        for cb in self.log_checks.values():
            cb.setChecked(not all_checked)
        self.select_all_btn.setText("Deselect All" if not all_checked else "Select All")

    def _get_selected_logs(self):
        return [name for name, cb in self.log_checks.items() if cb.isChecked()]

    def _get_severity_levels(self):
        idx = self.severity_combo.currentIndex()
        if idx == 0:
            return [1, 2]  # Critical, Error
        elif idx == 1:
            return [2, 3]  # Error, Warning
        else:
            return [1, 2, 3]  # All

    def _get_hours(self):
        return {0: 6, 1: 24, 2: 72, 3: 168, 4: 720}[self.time_combo.currentIndex()]

    def _quick_scan(self):
        # Quick scan: System log, last 24h, all severities
        for name, cb in self.log_checks.items():
            cb.setChecked(name == "System")
        self.time_combo.setCurrentIndex(1)
        self.severity_combo.setCurrentIndex(2)
        self._start_scan()

    def _start_scan(self):
        if self.scanner and self.scanner.isRunning():
            return
        
        selected_logs = self._get_selected_logs()
        if not selected_logs:
            QMessageBox.warning(self, "No Logs Selected", "Please select at least one event log to scan.")
            return
        
        hours = self._get_hours()
        levels = self._get_severity_levels()
        
        self.current_scan_info = f"Logs: {', '.join(selected_logs)} | Time: {self.time_combo.currentText()} | Severity: {self.severity_combo.currentText()}"
        
        self.scan_btn.setEnabled(False)
        self.quick_scan_btn.setEnabled(False)
        self.progress.show()
        self.progress.setValue(0)
        self.status_label.setText("Starting scan...")
        self.ai_summary.clear()
        self.raw_errors.clear()
        self.save_txt_btn.setEnabled(False)
        self.save_pdf_btn.setEnabled(False)
        
        self.scanner = EventLogScanner(selected_logs, hours, max_events=400, levels=levels)
        self.scanner.progress.connect(self.progress.setValue)
        self.scanner.status.connect(self.status_label.setText)
        self.scanner.finished.connect(self._on_scan_finished)
        self.scanner.start()

    @Slot(list, str)
    def _on_scan_finished(self, events, log_names):
        self.scan_btn.setEnabled(True)
        self.quick_scan_btn.setEnabled(True)
        
        # Deduplicate
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
        
        # Count by severity
        critical = sum(1 for e in unique_events if e.get('Level') == 1)
        errors = sum(1 for e in unique_events if e.get('Level') == 2)
        warnings = sum(1 for e in unique_events if e.get('Level') == 3)
        
        self.error_count_label.setText(
            f"🔴 {critical} critical | 🟠 {errors} errors | 🟡 {warnings} warnings | "
            f"({len(unique_events)} unique from {len(events)} total)"
        )
        
        if unique_events:
            # Display raw errors with color coding
            raw_lines = []
            for ev in unique_events:
                level = ev.get('Level', 3)
                icon = "🔴" if level == 1 else "🟠" if level == 2 else "🟡"
                raw_lines.append(
                    f"{icon} [{ev.get('Time', 'Unknown')}] {ev.get('LevelName', 'Event')} - {ev.get('Log', '')}\n"
                    f"   Source: {ev.get('Source', 'Unknown')} | Event ID: {ev.get('Id', 'N/A')}\n"
                    f"   {ev.get('Message', 'No message')}\n"
                )
            self.raw_errors.setPlainText("\n".join(raw_lines))
            self.save_txt_btn.setEnabled(True)
            self.save_pdf_btn.setEnabled(True)
            self.regenerate_btn.setEnabled(True)
            
            self._generate_ai_report()
        else:
            self.raw_errors.setPlainText("✅ No errors or warnings found in the selected time range!")
            self.ai_summary.setPlainText(
                "🎉 Great news! No issues were found.\n\n"
                "Your system appears to be running smoothly based on the event logs scanned. "
                "This is a good sign that your PC is healthy.\n\n"
                "Tip: Run periodic scans (weekly or monthly) to catch issues early."
            )
            self.progress.hide()

    def _generate_ai_report(self):
        if not self.current_events:
            return
        
        if not self.ai or not getattr(self.ai, 'is_loaded', False):
            self.ai_summary.setPlainText(
                "⚠️ AI Model Not Available\n\n"
                "To get an AI-powered analysis of these errors:\n"
                "1. Go to the AI Console tab\n"
                "2. Wait for a model to load\n"
                "3. Return here and click 'Regenerate'\n\n"
                "In the meantime, you can review the raw event log entries below."
            )
            self.progress.hide()
            return
        
        self.ai_summary.setPlainText("🔄 Generating AI analysis... This may take a moment.")
        self.regenerate_btn.setEnabled(False)
        self.progress.show()
        self.progress.setValue(0)
        
        self.ai_generator = AIReportGenerator(self.ai, self.current_events, self.current_scan_info)
        self.ai_generator.progress.connect(self.progress.setValue)
        self.ai_generator.status.connect(self.status_label.setText)
        self.ai_generator.finished.connect(self._on_ai_finished)
        self.ai_generator.start()

    @Slot(str)
    def _on_ai_finished(self, report):
        self.ai_summary.setPlainText(report)
        self.regenerate_btn.setEnabled(True)
        self.progress.hide()
        self.status_label.setText("✅ Analysis complete")

    # ---- Save/Export ----
    def _save_report(self, format_type="txt"):
        if not self.current_events and not self.ai_summary.toPlainText():
            return
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"SARA_Report_{timestamp}"
        
        if format_type == "pdf":
            self._export_pdf(default_name)
        else:
            self._export_txt(default_name)

    def _export_txt(self, default_name):
        # Save to reports folder automatically
        filename = REPORTS_DIR / f"{default_name}.txt"
        
        try:
            content = self._build_report_content()
            with open(filename, "w", encoding="utf-8") as f:
                f.write(content)
            
            QMessageBox.information(self, "Report Saved", f"Report saved to:\n{filename}")
            self._refresh_reports()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save report:\n{e}")

    def _export_pdf(self, default_name):
        # Let user choose location for PDF
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export PDF Report",
            str(REPORTS_DIR / f"{default_name}.pdf"),
            "PDF Files (*.pdf)"
        )
        
        if not file_path:
            return
        
        try:
            # Try using reportlab if available
            try:
                from reportlab.lib import colors
                from reportlab.lib.pagesizes import letter
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.units import inch
                from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
                
                self._create_pdf_reportlab(file_path)
                
            except ImportError:
                # Fallback: Create HTML and try to convert or just save as HTML
                html_path = file_path.replace('.pdf', '.html')
                self._create_html_report(html_path)
                QMessageBox.information(
                    self, "Exported as HTML",
                    f"reportlab not installed. Report saved as HTML:\n{html_path}\n\n"
                    "To enable PDF export, install reportlab:\npip install reportlab"
                )
                return
            
            QMessageBox.information(self, "PDF Exported", f"Report exported to:\n{file_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Could not export PDF:\n{e}")

    def _build_report_content(self):
        """Build the text content for the report."""
        lines = [
            "=" * 70,
            "SARA SYSTEM HEALTH REPORT",
            f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 70,
            "",
            f"Scan Settings: {self.current_scan_info}",
            "",
        ]
        
        # Count stats
        critical = sum(1 for e in self.current_events if e.get('Level') == 1)
        errors = sum(1 for e in self.current_events if e.get('Level') == 2)
        warnings = sum(1 for e in self.current_events if e.get('Level') == 3)
        
        lines.extend([
            f"Summary: {critical} Critical | {errors} Errors | {warnings} Warnings",
            f"Total Unique Events: {len(self.current_events)}",
            "",
            "=" * 70,
            "AI ANALYSIS",
            "=" * 70,
            "",
            self.ai_summary.toPlainText() or "No AI analysis available",
            "",
            "=" * 70,
            "RAW EVENT LOG ENTRIES",
            "=" * 70,
            "",
            self.raw_errors.toPlainText() or "No events recorded",
            "",
            "=" * 70,
            "END OF REPORT",
            "=" * 70,
        ])
        
        return "\n".join(lines)

    def _create_pdf_reportlab(self, file_path):
        """Create PDF using reportlab."""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Preformatted
        from reportlab.lib.enums import TA_CENTER
        
        doc = SimpleDocTemplate(file_path, pagesize=letter, 
                               rightMargin=50, leftMargin=50,
                               topMargin=50, bottomMargin=50)
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            spaceAfter=20,
            alignment=TA_CENTER
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=10,
            spaceBefore=15,
            textColor=colors.HexColor('#2c3e50')
        )
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=8,
            leading=14
        )
        mono_style = ParagraphStyle(
            'Mono',
            parent=styles['Code'],
            fontSize=8,
            leading=10,
            fontName='Courier'
        )
        
        story = []
        
        # Title
        story.append(Paragraph("SARA System Health Report", title_style))
        story.append(Paragraph(
            f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
            styles['Normal']
        ))
        story.append(Spacer(1, 20))
        
        # Summary
        story.append(Paragraph("Scan Summary", heading_style))
        story.append(Paragraph(f"Settings: {self.current_scan_info}", body_style))
        
        critical = sum(1 for e in self.current_events if e.get('Level') == 1)
        errors = sum(1 for e in self.current_events if e.get('Level') == 2)
        warnings = sum(1 for e in self.current_events if e.get('Level') == 3)
        story.append(Paragraph(
            f"Found: {critical} Critical, {errors} Errors, {warnings} Warnings ({len(self.current_events)} total unique events)",
            body_style
        ))
        story.append(Spacer(1, 15))
        
        # AI Analysis
        story.append(Paragraph("AI Analysis", heading_style))
        ai_text = self.ai_summary.toPlainText() or "No AI analysis available"
        # Split into paragraphs for better formatting
        for para in ai_text.split('\n\n'):
            if para.strip():
                # Escape special characters for reportlab
                safe_para = para.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                story.append(Paragraph(safe_para, body_style))
        story.append(Spacer(1, 15))
        
        # Raw Events (truncated for PDF)
        story.append(Paragraph("Event Log Entries (Summary)", heading_style))
        raw_text = self.raw_errors.toPlainText()
        if raw_text:
            # Limit raw events in PDF to keep file size reasonable
            lines = raw_text.split('\n')[:100]
            truncated = '\n'.join(lines)
            if len(raw_text.split('\n')) > 100:
                truncated += "\n\n... (truncated - see TXT export for full log)"
            story.append(Preformatted(truncated, mono_style))
        else:
            story.append(Paragraph("No events recorded", body_style))
        
        doc.build(story)

    def _create_html_report(self, file_path):
        """Create HTML report as fallback."""
        ai_text = self.ai_summary.toPlainText().replace('\n', '<br>')
        raw_text = self.raw_errors.toPlainText().replace('\n', '<br>').replace(' ', '&nbsp;')
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>SARA System Health Report</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; background: #f5f5f5; }}
        .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #6e8bff; padding-bottom: 15px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .meta {{ color: #7f8c8d; font-size: 14px; }}
        .summary {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin: 15px 0; }}
        .ai-analysis {{ background: #e8f4fd; padding: 20px; border-radius: 8px; border-left: 4px solid #6e8bff; }}
        .raw-events {{ background: #1a1a2e; color: #eee; padding: 15px; border-radius: 8px; font-family: 'Consolas', monospace; font-size: 11px; overflow-x: auto; }}
        .stats {{ display: flex; gap: 20px; margin: 15px 0; }}
        .stat {{ padding: 10px 20px; border-radius: 5px; color: white; }}
        .critical {{ background: #e74c3c; }}
        .error {{ background: #e67e22; }}
        .warning {{ background: #f39c12; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 SARA System Health Report</h1>
        <p class="meta">Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p class="meta">Scan: {self.current_scan_info}</p>
        
        <div class="stats">
            <span class="stat critical">🔴 {sum(1 for e in self.current_events if e.get('Level') == 1)} Critical</span>
            <span class="stat error">🟠 {sum(1 for e in self.current_events if e.get('Level') == 2)} Errors</span>
            <span class="stat warning">🟡 {sum(1 for e in self.current_events if e.get('Level') == 3)} Warnings</span>
        </div>
        
        <h2>🤖 AI Analysis</h2>
        <div class="ai-analysis">{ai_text or "No AI analysis available"}</div>
        
        <h2>📋 Raw Event Log Entries</h2>
        <div class="raw-events">{raw_text or "No events recorded"}</div>
    </div>
</body>
</html>"""
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html)

    # ---- Saved Reports Tab ----
    def _refresh_reports(self):
        self.report_list.clear()
        
        if not REPORTS_DIR.exists():
            REPORTS_DIR.mkdir(exist_ok=True)
        
        # Get both txt and pdf files
        files = list(REPORTS_DIR.glob("*.txt")) + list(REPORTS_DIR.glob("*.pdf")) + list(REPORTS_DIR.glob("*.html"))
        files = sorted(files, key=os.path.getmtime, reverse=True)
        
        if not files:
            item = QListWidgetItem("📭 No saved reports yet - run a scan to create one!")
            item.setFlags(Qt.NoItemFlags)
            self.report_list.addItem(item)
            return
        
        for f in files:
            mtime = datetime.datetime.fromtimestamp(f.stat().st_mtime)
            size_kb = f.stat().st_size / 1024
            ext = f.suffix.upper()[1:]
            icon = "📄" if ext == "PDF" else "📝" if ext == "TXT" else "🌐"
            label = f"{icon} {f.stem}  |  {ext}  |  {mtime.strftime('%Y-%m-%d %H:%M')}  |  {size_kb:.1f} KB"
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
        else:
            QMessageBox.warning(self, "Not Found", "This file no longer exists.")
            self._refresh_reports()

    def _open_reports_folder(self):
        try:
            if os.name == 'nt':
                os.startfile(REPORTS_DIR)
            else:
                webbrowser.open(str(REPORTS_DIR))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open folder:\n{e}")

    def _delete_report(self):
        item = self.report_list.currentItem()
        if not item or not item.data(Qt.UserRole):
            return
        
        path = item.data(Qt.UserRole)
        name = os.path.basename(path)
        
        reply = QMessageBox.question(
            self, "Delete Report",
            f"Are you sure you want to delete this report?\n\n{name}",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                os.remove(path)
                self._refresh_reports()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete file:\n{e}")