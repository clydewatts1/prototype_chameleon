#!/bin/bash
# Script to launch Streamlit server for Chameleon UI dashboards
#
# Usage: ./run_ui.sh [apps_dir] [port]
#
# Arguments:
#   apps_dir - Directory containing Streamlit dashboard files (default: ui_apps)
#   port     - Port to run Streamlit on (default: 8501)

# Set defaults
APPS_DIR="${1:-ui_apps}"
PORT="${2:-8501}"

# Create apps directory if it doesn't exist
mkdir -p "$APPS_DIR"

echo "========================================"
echo "Chameleon UI - Streamlit Server Launcher"
echo "========================================"
echo ""
echo "Apps Directory: $APPS_DIR"
echo "Port:          $PORT"
echo ""
echo "Starting Streamlit server..."
echo "Access dashboards at: http://localhost:$PORT"
echo ""
echo "Press Ctrl+C to stop the server"
echo "========================================"
echo ""

# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "❌ Error: Streamlit is not installed"
    echo "Install it with: pip install streamlit"
    exit 1
fi

# Run streamlit with the apps directory
# Note: Streamlit doesn't natively support multi-app directory browsing
# So we'll use a simple approach - run the first .py file found, or provide instructions

# Find the first .py file
FIRST_DASHBOARD=$(find "$APPS_DIR" -maxdepth 1 -name '*.py' -print -quit)

if [ -n "$FIRST_DASHBOARD" ]; then
    # If there are multiple dashboards, Streamlit will need a multipage app structure
    # For now, we'll launch streamlit with the first dashboard found
    streamlit run --server.port="$PORT" --server.address=localhost "$FIRST_DASHBOARD"
else
    echo "⚠️  No dashboard files found in $APPS_DIR"
    echo ""
    echo "Use the 'create_dashboard' tool to create a dashboard first."
    echo "Then run this script again."
    exit 1
fi
