#!/usr/bin/env python3
"""
Whisper Pro Electron App Launcher
Integrates with the Project Launcher system
"""

import subprocess
import sys
import shutil
from pathlib import Path


def launch_whisper():
    """Launch Whisper Pro Electron app"""
    script_dir = Path(__file__).parent

    # Try to run the built executable first (no npm required)
    exe_path = script_dir / "dist" / "Whisper-Pro-win32-x64" / "Whisper-Pro.exe"
    if exe_path.exists():
        subprocess.Popen(str(exe_path))
        return

    # Fallback: run npm start (requires npm in PATH)
    try:
        subprocess.Popen(
            [shutil.which('npm.cmd' if sys.platform == 'win32' else 'npm')
             or ('npm.cmd' if sys.platform == 'win32' else 'npm'), 'start'],
            cwd=str(script_dir),
            creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
        )
    except Exception as e:
        print(f"Error launching Whisper Pro: {e}")
        sys.exit(1)


if __name__ == "__main__":
    launch_whisper()
