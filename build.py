"""
Automated Build Script for Retail POS Desktop Executable.
Runs PyInstaller using the customized RetailPOS.spec.
"""
import subprocess
import sys


def build_exe():
    print("==================================================")
    print(" Building Standalone Retail POS Windows Executable")
    print("==================================================")

    # 1. Ensure PyInstaller is installed
    try:
        import PyInstaller
        print(f"PyInstaller {PyInstaller.__version__} detected.")
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 2. Run PyInstaller
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "RetailPOS.spec",
        "--clean",
        "--noconfirm"
    ]
    print(f"Executing: {' '.join(cmd)}")
    subprocess.check_call(cmd)

    print("\n✅ Build Complete! Executable is located in:")
    print("   dist/RetailPOS.exe\n")


if __name__ == "__main__":
    build_exe()
