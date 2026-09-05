#!/bin/bash
set -e
echo "Building PanopticonSymphony for Linux..."
pip3 install -r requirements.txt
pip3 install pyinstaller
pyinstaller --noconfirm --name PanopticonSymphony --onefile \
    --add-data "camera_sources.json:." \
    --add-data "video_analyzer.py:." \
    --add-data "music_generator.py:." \
    main.py
cp camera_sources.json dist/ 2>/dev/null || true
echo "Done: dist/PanopticonSymphony"