@echo off
echo Building PanopticonSymphony...
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --noconfirm --name PanopticonSymphony --windowed --onefile ^
    --add-data "camera_sources.json;." ^
    --add-data "video_analyzer.py;." ^
    --add-data "music_generator.py;." ^
    main.py
copy camera_sources.json dist\camera_sources.json
echo Done: dist\PanopticonSymphony.exe
pause