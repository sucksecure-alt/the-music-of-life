#!/bin/bash
# ═══════════════════════════════════════════════════
#  PANOPTICON SYMPHONY — DMG CRAFTER
#  Они не узнают, откуда идёт музыка.
# ═══════════════════════════════════════════════════

APP_NAME="PanopticonSymphony"
VERSION="1.0.0"
DIST_DIR="dist"
BUILD_DIR="build"

echo "◉ CRAFTING ${APP_NAME} v${VERSION}"
echo "  they do not know they are playing"
echo ""

# 1. Проверка зависимостей
echo "[1/5] Checking dependencies..."
python3 -c "import cv2, numpy, sounddevice, PyQt5, yt_dlp" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "  Installing dependencies..."
    pip3 install -r requirements.txt
    brew install portaudio ffmpeg 2>/dev/null
fi

# 2. Создание структуры .app
echo "[2/5] Building application bundle..."
rm -rf "${DIST_DIR}/${APP_NAME}.app"
mkdir -p "${DIST_DIR}/${APP_NAME}.app/Contents/MacOS"
mkdir -p "${DIST_DIR}/${APP_NAME}.app/Contents/Resources"
mkdir -p "${DIST_DIR}/${APP_NAME}.app/Contents/Frameworks"

# 3. Копирование файлов
echo "[3/5] Copying source files..."
cp main.py "${DIST_DIR}/${APP_NAME}.app/Contents/Resources/"
cp video_analyzer.py "${DIST_DIR}/${APP_NAME}.app/Contents/Resources/"
cp music_generator.py "${DIST_DIR}/${APP_NAME}.app/Contents/Resources/"
cp camera_sources.json "${DIST_DIR}/${APP_NAME}.app/Contents/Resources/"

# 4. Создание Info.plist
echo "[4/5] Writing manifest..."
cat > "${DIST_DIR}/${APP_NAME}.app/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
 "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>PanopticonSymphony</string>
    <key>CFBundleDisplayName</key>
    <string>Panopticon Symphony</string>
    <key>CFBundleIdentifier</key>
    <string>com.heartbleed.panopticon</string>
    <key>CFBundleVersion</key>
    <string>1.0.0</string>
    <key>CFBundleExecutable</key>
    <string>launcher</string>
    <key>CFBundleIconFile</key>
    <string>icon</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST

# 5. Создание лаунчера
cat > "${DIST_DIR}/${APP_NAME}.app/Contents/MacOS/launcher" << 'LAUNCHER'
#!/bin/bash
DIR="$(cd "$(dirname "$0")/../Resources" && pwd)"
cd "$DIR"
python3 main.py
LAUNCHER
chmod +x "${DIST_DIR}/${APP_NAME}.app/Contents/MacOS/launcher"

# 6. Создание DMG
echo "[5/5] Sealing the DMG..."
rm -f "${APP_NAME}.dmg"
hdiutil create \
    -volname "${APP_NAME}" \
    -srcfolder "${DIST_DIR}/${APP_NAME}.app" \
    -ov \
    -format UDZO \
    "${APP_NAME}.dmg"

echo ""
echo "◉ DONE: ${APP_NAME}.dmg"
echo "  Open it. Let them sing."