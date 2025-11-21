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

if __name__ == "__main__":
    if is_admin():
        # ✅ We have admin privileges - launch main.py
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)
        main_script = os.path.join(script_dir, "main.py")

        print(f"🚀 Launching SARA with admin privileges...")
        print(f"📁 Working directory: {script_dir}")
        print(f"📄 Main script: {main_script}")

        # Use subprocess.run to WAIT for the process (keeps window open)
        # Or use Popen with .wait() if you need more control
        try:
            result = subprocess.run(
                [sys.executable, main_script], 
                cwd=script_dir,
                capture_output=False  # Show output in console
            )
            print(f"✅ SARA exited with code: {result.returncode}")
        except Exception as e:
            print(f"❌ Error launching SARA: {e}")
            input("Press Enter to close...")  # Keep window open on error
            
    else:
        # 🧩 Relaunch this script with admin privileges
        print("🔐 Requesting admin privileges...")
        script_path = os.path.abspath(__file__)
        
        # ShellExecuteW returns a value > 32 if successful
        result = ctypes.windll.shell32.ShellExecuteW(
            None,           # hwnd
            "runas",        # operation (run as admin)
            sys.executable, # program (python.exe)
            f'"{script_path}"',  # parameters
            None,           # directory
            1               # show command (SW_SHOWNORMAL)
        )
        
        if result <= 32:
            print(f"❌ Failed to get admin privileges. Error code: {result}")
            input("Press Enter to close...")
        
        sys.exit()