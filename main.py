"""
SARA - AI Repair Agent
Direct Python-based styling (no .qss dependency)
Configured for local AI integration
"""

import sys
import os
import ctypes
import traceback
import threading
from datetime import datetime
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow


def is_admin():
    """Check if script has admin privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def run_as_admin():
    """Re-launch this script with admin privileges."""
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{__file__}"', None, 1
    )
    sys.exit(0)

def exception_hook(exctype, value, tb):
    """Catch all unhandled exceptions."""
    print(f"\n{'='*60}")
    print(f"⚠️ UNHANDLED EXCEPTION at {datetime.now()}")
    print(f"{'='*60}")
    print(f"Type: {exctype.__name__}")
    print(f"Value: {value}")
    print(f"\nTraceback:")
    traceback.print_tb(tb)
    print(f"{'='*60}\n")
    
    # Don't exit immediately - let Qt cleanup
    try:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            print("Attempting graceful shutdown...")
            app.quit()
    except:
        pass

# Thread exception handler
def thread_exception_hook(args):
    """Catch exceptions in threads."""
    print(f"\n{'='*60}")
    print(f"⚠️ THREAD EXCEPTION at {datetime.now()}")
    print(f"{'='*60}")
    print(f"Thread: {args.thread}")
    print(f"Type: {args.exc_type.__name__}")
    print(f"Value: {args.exc_value}")
    if args.exc_traceback:
        print(f"\nTraceback:")
        traceback.print_tb(args.exc_traceback)
    print(f"{'='*60}\n")

# Install handlers
sys.excepthook = exception_hook
threading.excepthook = thread_exception_hook

# ------------------------------
# Inline Stylesheet
# ------------------------------
GLOBAL_STYLE = """
QWidget {
    background-color: #0f1117;
    color: #e8eef6;
    font-family: 'Segoe UI', sans-serif;
    font-size: 14px;
}

QPushButton {
    background-color: #1b2230;
    color: #e8eef6;
    border: 1px solid #2b3548;
    border-radius: 10px;
    padding: 8px 14px;
    margin: 8px 10px;
    text-align: left;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #233048;
    border-color: #6e8bff;
}
QPushButton:pressed {
    background-color: #151c29;
    border-color: #94a8ff;
}

QLabel {
    color: #e8eef6;
}

QLabel#title {
    font-size: 28px;
    font-weight: 700;
    color: #ffffff;
}

QLabel#subtitle {
    font-size: 14px;
    color: #9eb3ff;
    margin-bottom: 10px;
}

QGroupBox {
    background: #121826;
    border: 1px solid #2b3548;
    border-radius: 14px;
    padding: 16px;
}

QLineEdit, QTextEdit, QComboBox {
    background: #0f1522;
    color: #e8eef6;
    border: 1px solid #2b3548;
    border-radius: 8px;
    padding: 6px 8px;
}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border-color: #6e8bff;
}

QTabBar::tab {
    background: #141b2a;
    color: #c9d3ec;
    padding: 8px 14px;
    border: 1px solid #2b3548;
    border-bottom: none;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
}
QTabBar::tab:selected {
    background: #1a2334;
    color: #ffffff;
    border-color: #6e8bff;
}

QProgressBar {
    background: #131a28;
    border: 1px solid #2b3548;
    border-radius: 10px;
    text-align: center;
    color: #e8eef6;
    min-height: 20px;
}
QProgressBar::chunk {
    background: #37c871;
    border-radius: 9px;
    margin: 2px;
}

QScrollArea {
    border: none;
}

QCheckBox {
    color: #e8eef6;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #2b3548;
    border-radius: 4px;
    background: #0f1522;
}

QCheckBox::indicator:checked {
    background: #6e8bff;
    border-color: #6e8bff;
}

QSpinBox {
    background: #0f1522;
    color: #e8eef6;
    border: 1px solid #2b3548;
    border-radius: 6px;
    padding: 4px 8px;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #2b3548;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #6e8bff;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}

QSlider::handle:horizontal:hover {
    background: #869eff;
}
"""


def main():
    print("🚀 Starting SARA (AI Repair Agent)...")
    print(f"📍 Admin privileges: {is_admin()}")
    
    # Track active threads
    print(f"📊 Active threads at start: {threading.active_count()}")
    
    try:
        app = QApplication(sys.argv)
        print("🧭 QApplication created")

        # Apply style directly here
        app.setStyleSheet(GLOBAL_STYLE)
        print("✅ Inline stylesheet applied (no .qss needed).")

        window = MainWindow()
        window.show()
        print("✅ MainWindow created and visible.")
        
        # Monitor threads periodically
        def print_thread_count():
            count = threading.active_count()
            if count > 5:  # Alert if too many threads
                print(f"⚠️ Warning: {count} threads active")
                for t in threading.enumerate():
                    print(f"  - {t.name}: {t.is_alive()}")
        
        # Check every 10 seconds
        from PySide6.QtCore import QTimer
        monitor = QTimer()
        monitor.timeout.connect(print_thread_count)
        monitor.start(10000)
        
        print(f"📊 Entering event loop with {threading.active_count()} threads")
        result = app.exec()
        
        print(f"\n📊 App exited with code {result}")
        print(f"📊 Threads at exit: {threading.active_count()}")
        for t in threading.enumerate():
            print(f"  - {t.name}: alive={t.is_alive()}, daemon={t.daemon}")
        
        return result
        
    except Exception as e:
        print(f"❌ Fatal Error: {e}")
        traceback.print_exc()
        return 1
    finally:
        print("🛑 Cleanup phase...")
        # Force thread cleanup
        for t in threading.enumerate():
            if t != threading.main_thread() and t.is_alive() and not t.daemon:
                print(f"⚠️ Non-daemon thread still alive: {t.name}")
                try:
                    t.join(timeout=1.0)
                except:
                    pass


if __name__ == "__main__":
    # Check for admin privileges and request if needed
    if not is_admin():
        print("🔐 Requesting admin privileges...")
        run_as_admin()
    
    # Set working directory to script location
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    exit_code = main()
    print(f"\n{'='*60}")
    print(f"🏁 SARA exiting with code {exit_code}")
    print(f"📊 Final thread count: {threading.active_count()}")
    print(f"{'='*60}\n")
    sys.exit(exit_code)