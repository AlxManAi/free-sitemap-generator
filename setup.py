import subprocess
import sys
import os
from pathlib import Path

# Configuration for the build
APP_NAME = "ALXSitemapGenerator"  # Name for the output executable (without .exe suffix)
SCRIPT_NAME = "main.py"       # The main Python script to package
VERSION = "2.0.0"             # Application version

def check_and_install_pyinstaller():
    """Check if PyInstaller is installed, install if not."""
    try:
        import PyInstaller
        print("✓ PyInstaller is installed")
        return True
    except ImportError:
        print("⚠ PyInstaller is not installed. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"], 
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("✓ PyInstaller installed successfully")
            return True
        except Exception as e:
            print(f"✗ Failed to install PyInstaller: {e}")
            print("Please install manually: pip install pyinstaller")
            return False


def build_executable():
    """
    Builds a standalone executable from the specified Python script using PyInstaller.
    """
    print("=" * 70)
    print(f"Building {APP_NAME} v{VERSION}")
    print("=" * 70)
    print(f"Main script: {SCRIPT_NAME}\n")
    
    # Check and install PyInstaller if needed
    if not check_and_install_pyinstaller():
        return
    print()

    # Check if icon exists
    icon_path = os.path.join("assets", "icon", "app.ico")
    icon_arg = []
    if os.path.exists(icon_path):
        icon_arg = [f"--icon={icon_path}"]
        print(f"✓ Using icon: {icon_path}")
    else:
        print(f"⚠ Warning: Icon not found at {icon_path}, building without icon")

    # Check if theme file exists
    theme_path = "dark_theme.qss"
    theme_data_arg = []
    if os.path.exists(theme_path):
        # Format: "source_path;destination_path"
        if sys.platform == "win32":
            theme_data_arg = [f"--add-data={theme_path};."]
        else:
            theme_data_arg = [f"--add-data={theme_path}:."]
        print(f"✓ Including theme file: {theme_path}")

    # Build PyInstaller command with all necessary options
    pyinstaller_command = [
        sys.executable,           # Path to the current Python interpreter
        "-m", "PyInstaller",      # Run PyInstaller as a module
        "--onefile",              # Create a single executable file
        "--clean",                # Clean PyInstaller cache
        f"--name={APP_NAME}",     # Executable name
        *icon_arg,                # Add icon if available
        *theme_data_arg,          # Add theme file if available
    ]
    
    # Add OS-specific options
    if sys.platform == "win32":
        pyinstaller_command.append("--windowed")  # No console window on Windows
        # Add version file if exists (Windows only)
        if os.path.exists("version_info.txt"):
            pyinstaller_command.append("--version-file=version_info.txt")
    else:
        pyinstaller_command.append("--noconsole")  # No console on other systems
    
    # Add common options
    pyinstaller_command.extend([
        # Hidden imports for PyQt6 and other modules
        "--hidden-import=PyQt6.QtCore",
        "--hidden-import=PyQt6.QtGui",
        "--hidden-import=PyQt6.QtWidgets",
        "--hidden-import=sitemap_generator",
        "--hidden-import=url_normalizer",
        
        # Collect all PyQt6 plugins (needed for some features)
        "--collect-all=PyQt6",
        
        # Application script
        SCRIPT_NAME
    ])


    print(f"\nRunning PyInstaller command...")
    print(f"Command: {' '.join(pyinstaller_command[:5])} ... [truncated]")
    print("-" * 70)

    try:
        # Execute the PyInstaller command
        # Don't capture output to see progress in real-time
        process = subprocess.run(pyinstaller_command, check=True)
        
        print("\n" + "=" * 70)
        print("✓ BUILD SUCCESSFUL")
        print("=" * 70)
        
        # Determine the executable extension based on the OS
        exe_suffix = ".exe" if sys.platform == "win32" else ""
        executable_path = os.path.join(os.getcwd(), "dist", APP_NAME + exe_suffix)
        
        # Check if file exists and get size
        if os.path.exists(executable_path):
            file_size = os.path.getsize(executable_path)
            file_size_mb = file_size / (1024 * 1024)
            print(f"✓ Executable created: {executable_path}")
            print(f"✓ File size: {file_size_mb:.2f} MB ({file_size:,} bytes)")
            print(f"\nYou can now run the application from: {executable_path}")
        else:
            print(f"⚠ Warning: Expected executable not found at {executable_path}")
            print("Please check the 'dist' directory for the output file.")
        
    except subprocess.CalledProcessError as e:
        print("\n-------------------- BUILD FAILED --------------------")
        print("PyInstaller encountered an error.")
        print(f"Return code: {e.returncode}")
        if e.stdout:
            print("\nPyInstaller Output (stdout):\n", e.stdout)
        if e.stderr:
            print("\nPyInstaller Output (stderr):\n", e.stderr)
        print("\nTroubleshooting tips:")
        print("1. Ensure PyInstaller is installed and up-to-date ('pip install --upgrade pyinstaller').")
        print("2. Check that all dependencies of main.py (e.g., PyQt6, requests, beautifulsoup4) are installed in the environment.")
        print("3. If you have specific PyQt6 plugins or data files, you might need to use --add-data or --collect-all options.")
        print("4. Review the full output above for specific error messages from PyInstaller.")
        
    except FileNotFoundError:
        print("\n-------------------- BUILD FAILED --------------------")
        print("Error: PyInstaller command not found.")
        print(f"Attempted to run: {pyinstaller_command[0]} -m PyInstaller ...")
        print("Please ensure PyInstaller is installed and that the Python environment (sys.executable) is correctly configured.")
        print(f"Python interpreter being used: {sys.executable}")

    except Exception as e:
        print("\n-------------------- AN UNEXPECTED ERROR OCCURRED --------------------")
        print(f"An error of type {type(e).__name__} occurred: {e}")


if __name__ == "__main__":
    # Create a 'dist' directory if it doesn't exist, as PyInstaller will output there.
    # This is not strictly necessary as PyInstaller creates it, but can be good practice.
    if not os.path.exists("dist"):
        os.makedirs("dist", exist_ok=True)
        
    build_executable()
