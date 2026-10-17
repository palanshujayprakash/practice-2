"""
Desktop POS Application Launcher.
Spawns the Streamlit POS backend in the background and renders it in a native pywebview desktop window.
Handles graceful shutdown when the application window is closed.
"""
import os
import sys
import time
import socket
import subprocess
import urllib.request
from pathlib import Path
import webview


def get_base_path() -> Path:
    """Get absolute path to resource, works for dev and for PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def find_free_port(default_port: int = 8501) -> int:
    """Check if default port is free, otherwise select an open ephemeral port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", default_port)) != 0:
            return default_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def wait_for_server(url: str, timeout: float = 20.0) -> bool:
    """Poll the Streamlit HTTP server until it responds or times out."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    base_dir = get_base_path()
    os.chdir(base_dir)

    port = find_free_port(8501)
    server_url = f"http://127.0.0.1:{port}"

    # Prepare Streamlit launch arguments
    app_script = str(base_dir / "app.py")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        app_script,
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--server.enableCORS",
        "false",
        "--server.enableXsrfProtection",
        "false",
        "--client.toolbarMode",
        "minimal",
        "--browser.gatherUsageStats",
        "false",
    ]

    # Windows creation flag to prevent secondary console window
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NO_WINDOW

    print(f"Starting Streamlit backend on {server_url}...")
    server_proc = subprocess.Popen(
        cmd,
        cwd=str(base_dir),
        env=env,
        creationflags=creation_flags
    )

    try:
        # Wait until server is ready
        if not wait_for_server(server_url, timeout=25.0):
            print("Warning: Streamlit server took longer than expected to start. Launching window...")

        icon_path = base_dir / "assets" / "icon.ico"
        icon_arg = str(icon_path) if icon_path.exists() else None

        # Create Native Desktop Window
        window = webview.create_window(
            title="Retail POS - Offline Billing & Inventory",
            url=server_url,
            width=1366,
            height=768,
            min_size=(1024, 600),
            confirm_close=False,
            text_select=True,
        )

        # Run pywebview event loop (blocks until window is closed)
        webview.start(debug=False)

    finally:
        # Gracefully terminate background Streamlit server on window close
        print("Closing application...")
        try:
            server_proc.terminate()
            server_proc.wait(timeout=3.0)
        except Exception:
            try:
                server_proc.kill()
            except Exception:
                pass


if __name__ == "__main__":
    main()
