#!/usr/bin/env bash

# Exit on error
set -euo pipefail

echo "🥛 Building Ayran Notes AppImage..."

# Get absolute paths
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKAGING_DIR="${PROJECT_ROOT}/packaging"
BUILD_DIR="${PACKAGING_DIR}/build"
APPDIR="${PACKAGING_DIR}/Ayran-Notes.AppDir"
DIST_DIR="${PROJECT_ROOT}/dist"
APP_VERSION="$(sed -n 's/^version = "\([^"]*\)"/\1/p' "${PROJECT_ROOT}/pyproject.toml" | head -n 1)"

cd "$PROJECT_ROOT"

# Check required tools
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is required but not installed."
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
PYTHON_RUNNER="${BUILD_DIR}/venv/bin/python"
if command -v uv &> /dev/null; then
    uv venv --python 3.13 "${BUILD_DIR}/venv"
else
    python3 -m venv "${BUILD_DIR}/venv"
fi

echo "📦 Installing dependencies..."
if command -v uv &> /dev/null; then
    uv pip install --python "${PYTHON_RUNNER}" "${PROJECT_ROOT}[build]"
else
    "${PYTHON_RUNNER}" -m pip install "${PROJECT_ROOT}[build]"
fi

echo "🏗️ Building with PyInstaller..."
cd "$PACKAGING_DIR"
"${PYTHON_RUNNER}" -m PyInstaller ayrannotes.spec --workpath="${BUILD_DIR}/pyinstaller_build" --distpath="${BUILD_DIR}/pyinstaller_dist"

echo "📁 Creating AppDir structure..."
cd "$PROJECT_ROOT"

# Create standard AppDir directories
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/lib"
mkdir -p "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

# Copy PyInstaller output to usr/bin
cp -r "${BUILD_DIR}/pyinstaller_dist/ayrannotes/"* "${APPDIR}/usr/bin/"

# Copy AppRun
cp "${PACKAGING_DIR}/AppRun" "${APPDIR}/AppRun"
chmod +x "${APPDIR}/AppRun"

# Copy desktop file and icon
cp ayrannotes.desktop "${APPDIR}/ayrannotes.desktop"
cp ayrannotes.desktop "${APPDIR}/usr/share/applications/ayrannotes.desktop"
cp ayrannotes/assets/ayrannotes.png "${APPDIR}/ayrannotes.png"
cp ayrannotes/assets/ayrannotes.png "${APPDIR}/usr/share/icons/hicolor/256x256/apps/ayrannotes.png"

echo "🐧 Preparing verified linuxdeploy..."
cd "$PACKAGING_DIR"
LINUXDEPLOY_VERSION="1-alpha-20251107-1"
LINUXDEPLOY_SHA256="c20cd71e3a4e3b80c3483cef793cda3f4e990aca14014d23c544ca3ce1270b4d"
LINUXDEPLOY="linuxdeploy-${LINUXDEPLOY_VERSION}-x86_64.AppImage"
if [ ! -f "$LINUXDEPLOY" ]; then
    wget --https-only -q \
        "https://github.com/linuxdeploy/linuxdeploy/releases/download/${LINUXDEPLOY_VERSION}/linuxdeploy-x86_64.AppImage" \
        -O "$LINUXDEPLOY"
fi
echo "${LINUXDEPLOY_SHA256}  ${LINUXDEPLOY}" | sha256sum --check --status || {
    echo "❌ Error: linuxdeploy SHA-256 verification failed." >&2
    exit 1
}
chmod +x "$LINUXDEPLOY"

echo "🖼️ Generating AppImage..."
export ARCH=x86_64
APPIMAGE_EXTRACT_AND_RUN=1 "./${LINUXDEPLOY}" --appdir "${APPDIR}" --output appimage

# Move to dist
mv Ayran_Notes-*.AppImage "${DIST_DIR}/Ayran-Notes-${APP_VERSION}-x86_64.AppImage"

echo "✅ Build complete! AppImage is available at ${DIST_DIR}/Ayran-Notes-${APP_VERSION}-x86_64.AppImage"
