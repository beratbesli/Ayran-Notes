#!/bin/bash
set -e

echo "🥛 Building Ayran Notes .deb package..."

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGING_DIR="${PROJECT_ROOT}/packaging"
BUILD_DIR="${PACKAGING_DIR}/build"
DEB_DIR="${BUILD_DIR}/ayrannotes_deb"
DIST_DIR="${PROJECT_ROOT}/dist"

# Check if PyInstaller build exists
if [ ! -d "${BUILD_DIR}/pyinstaller_dist/ayrannotes" ]; then
    echo "❌ Error: PyInstaller build not found. Run AppImage build first."
    exit 1
fi

rm -rf "$DEB_DIR"
mkdir -p "${DEB_DIR}/opt/ayrannotes"
mkdir -p "${DEB_DIR}/usr/share/applications"
mkdir -p "${DEB_DIR}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${DEB_DIR}/usr/bin"
mkdir -p "${DEB_DIR}/DEBIAN"

echo "📦 Copying files..."
cp -r "${BUILD_DIR}/pyinstaller_dist/ayrannotes/"* "${DEB_DIR}/opt/ayrannotes/"
cp "${PROJECT_ROOT}/ayrannotes.desktop" "${DEB_DIR}/usr/share/applications/"
cp "${PROJECT_ROOT}/ayrannotes/assets/ayrannotes.png" "${DEB_DIR}/usr/share/icons/hicolor/256x256/apps/"

# Create a symlink so the user can type 'ayrannotes' in the terminal
ln -s /opt/ayrannotes/ayrannotes "${DEB_DIR}/usr/bin/ayrannotes"

# Update desktop file Exec path for system-wide installation
sed -i 's/^Exec=.*/Exec=\/opt\/ayrannotes\/ayrannotes/' "${DEB_DIR}/usr/share/applications/ayrannotes.desktop"

echo "📝 Creating control file..."
cat << 'CONTROL' > "${DEB_DIR}/DEBIAN/control"
Package: ayrannotes
Version: 1.0.0
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Berat Besli
Description: A lightweight, customizable, and modern note-taking application for Linux.
 Built with Python 3 and PyQt6. Features Markdown support, LLM integration, and Git versioning.
CONTROL

echo "🔨 Building .deb package..."
mkdir -p "${DIST_DIR}"
dpkg-deb --build "$DEB_DIR" "${DIST_DIR}/Ayran-Notes-amd64.deb"

echo "✅ Build complete! .deb package is available at ${DIST_DIR}/Ayran-Notes-amd64.deb"
