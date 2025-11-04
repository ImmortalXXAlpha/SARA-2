import subprocess
import threading

def run_command(command, callback=None):
    """Run a system command in a background thread."""
    def task():
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            output = result.stdout.strip() or result.stderr.strip() or "Command completed."
        except Exception as e:
            output = f"Error: {e}"
        if callback:
            callback(output)
    threading.Thread(target=task, daemon=True).start()
