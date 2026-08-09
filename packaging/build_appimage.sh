#!/bin/bash

# Exit on error
set -e

echo "🍺 Building Beer Notes AppImage..."

# Get absolute paths
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGING_DIR="${PROJECT_ROOT}/packaging"
BUILD_DIR="${PACKAGING_DIR}/build"
APPDIR="${PACKAGING_DIR}/Beer-Notes.AppDir"
DIST_DIR="${PROJECT_ROOT}/dist"

cd "$PROJECT_ROOT"

# Check required tools
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is required but not installed."
    exit 1
fi

if ! command -v pip &> /dev/null; then
    echo "❌ Error: pip is required but not installed."
    exit 1
fi

if ! command -v wget &> /dev/null; then
    echo "❌ Error: wget is required but not installed."
    exit 1
fi

echo "🧹 Cleaning up previous builds..."
rm -rf "$BUILD_DIR"
rm -rf "$APPDIR"
mkdir -p "$BUILD_DIR"
mkdir -p "$APPDIR"
mkdir -p "$DIST_DIR"

echo "🐍 Setting up virtual environment..."
python3 -m venv "${BUILD_DIR}/venv"
source "${BUILD_DIR}/venv/bin/activate"

echo "📦 Installing dependencies..."
pip install -r requirements.txt
pip install pyinstaller

echo "🏗️ Building with PyInstaller..."
cd "$PACKAGING_DIR"
pyinstaller beernotes.spec --workpath="${BUILD_DIR}/pyinstaller_build" --distpath="${BUILD_DIR}/pyinstaller_dist"

echo "📁 Creating AppDir structure..."
cd "$PROJECT_ROOT"

# Create standard AppDir directories
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/lib"
mkdir -p "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

# Copy PyInstaller output to usr/bin
cp -r "${BUILD_DIR}/pyinstaller_dist/beernotes/"* "${APPDIR}/usr/bin/"

# Copy AppRun
cp "${PACKAGING_DIR}/AppRun" "${APPDIR}/AppRun"
chmod +x "${APPDIR}/AppRun"

# Copy desktop file and icon
cp beernotes.desktop "${APPDIR}/beernotes.desktop"
cp beernotes.desktop "${APPDIR}/usr/share/applications/beernotes.desktop"
cp beernotes/assets/beernotes.png "${APPDIR}/beernotes.png"
cp beernotes/assets/beernotes.png "${APPDIR}/usr/share/icons/hicolor/256x256/apps/beernotes.png"

echo "🐧 Downloading linuxdeploy..."
cd "$PACKAGING_DIR"
if [ ! -f "linuxdeploy-x86_64.AppImage" ]; then
    wget -q https://github.com/linuxdeploy/linuxdeploy/releases/download/continuous/linuxdeploy-x86_64.AppImage
    chmod +x linuxdeploy-x86_64.AppImage
fi

echo "🖼️ Generating AppImage..."
export ARCH=x86_64
./linuxdeploy-x86_64.AppImage --appdir "${APPDIR}" --output appimage

# Move to dist
mv Beer_Notes-*.AppImage "${DIST_DIR}/Beer-Notes-x86_64.AppImage"

echo "✅ Build complete! AppImage is available at ${DIST_DIR}/Beer-Notes-x86_64.AppImage"
