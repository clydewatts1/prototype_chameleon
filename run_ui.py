#!/usr/bin/env python3
"""
Python script to launch Streamlit server for Chameleon UI dashboards.

Usage:
    python run_ui.py [apps_dir] [port]

Arguments:
    apps_dir - Directory containing Streamlit dashboard files (default: ui_apps)
    port     - Port to run Streamlit on (default: 8501)
"""

import sys
import os
import subprocess
from pathlib import Path

# Add server directory to path to import config module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "server"))

try:
    from config import load_config
    config = load_config()
    ui_config = config.get('features', {}).get('chameleon_ui', {})
    default_apps_dir = ui_config.get('apps_dir', 'ui_apps')
except Exception as e:
    print(f"Warning: Could not load config, using defaults: {e}")
    default_apps_dir = 'ui_apps'


def main():
    """Main entry point for the Streamlit launcher."""
    # Parse command-line arguments
    apps_dir = sys.argv[1] if len(sys.argv) > 1 else default_apps_dir
    port = sys.argv[2] if len(sys.argv) > 2 else '8501'
    
    # Convert to absolute path
    apps_dir_path = Path(apps_dir).absolute()
    
    # Create apps directory if it doesn't exist
    apps_dir_path.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("Chameleon UI - Streamlit Server Launcher")
    print("=" * 60)
    print()
    print(f"Apps Directory: {apps_dir_path}")
    print(f"Port:           {port}")
    print()
    print("Starting Streamlit server...")
    print(f"Access dashboards at: http://localhost:{port}")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    print()
    
    # Check if streamlit is installed
    try:
        subprocess.run(['streamlit', '--version'], 
                      capture_output=True, 
                      check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Error: Streamlit is not installed")
        print("Install it with: pip install streamlit")
        sys.exit(1)
    
    # Find all Python files in the apps directory
    dashboard_files = list(apps_dir_path.glob('*.py'))
    
    if not dashboard_files:
        print(f"⚠️  No dashboard files found in {apps_dir_path}")
        print()
        print("Use the 'create_dashboard' tool to create a dashboard first.")
        print("Then run this script again.")
        sys.exit(1)
    
    print(f"Found {len(dashboard_files)} dashboard(s):")
    for i, dashboard in enumerate(dashboard_files, 1):
        print(f"  {i}. {dashboard.name}")
    print()
    
    # Launch streamlit with the first dashboard
    # Note: For multiple dashboards, consider creating a multipage app structure
    first_dashboard = dashboard_files[0]
    
    print(f"Launching: {first_dashboard.name}")
    print()
    
    try:
        # Change to apps directory and run streamlit
        os.chdir(apps_dir_path)
        subprocess.run([
            'streamlit', 'run',
            str(first_dashboard),
            '--server.port', port,
            '--server.address', 'localhost'
        ])
    except KeyboardInterrupt:
        print("\n\nStreamlit server stopped.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error running Streamlit: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
