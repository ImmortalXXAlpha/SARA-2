import sys
import os
import ctypes
import subprocess

def is_admin():
    """Check if script has admin privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if is_admin():
    # ✅ Launch main.py from the same folder, keep GUI open
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    main_script = os.path.join(script_dir, "main.py")

    # Use Popen so it stays running (not blocking like run)
    subprocess.Popen([sys.executable, main_script], cwd=script_dir)
else:
    # 🧩 Relaunch this script with admin privileges
    params = f'"{os.path.abspath(__file__)}"'
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    sys.exit()  # Exit the non-admin instance