@echo off
echo [*] Fetching current date...
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "Get-Date -Format 'yyyy-MM-dd'"`) do set "CURRENT_DATE=%%i"

:: Update build date in translations.json and web/app.py
python scratch/update_translations_date.py

echo [*] Initializing KM Print Fix Hub (FULL VERSION) build...
set "BUILD_FULL_VERSION_DIR=Build_full\KM Print Fix Hub"

:: 1. Clear old files in builds (preserving .git and other repository metadata)
if not exist "%BUILD_FULL_VERSION_DIR%" goto skip_clean_full
echo [*] Cleaning old files in Full build folder (preserving .git)...
for %%d in (web search llm config preprocessing embeddings vector_store reranker history static templates Index Archive Service_manuals kb) do (
    if exist "%BUILD_FULL_VERSION_DIR%\%%d" rmdir /s /q "%BUILD_FULL_VERSION_DIR%\%%d"
)
for %%f in (.gitignore README.md start.bat README.txt related_models.json translations.json requirements.txt index_pdfs.py settings.json) do (
    if exist "%BUILD_FULL_VERSION_DIR%\%%f" del /f /q "%BUILD_FULL_VERSION_DIR%\%%f"
)
:skip_clean_full

:: 2. Create Full folder structure
echo [*] Creating Full version folder structure...
if not exist Build_full mkdir Build_full
if not exist "%BUILD_FULL_VERSION_DIR%" mkdir "%BUILD_FULL_VERSION_DIR%"
mkdir "%BUILD_FULL_VERSION_DIR%\web"
mkdir "%BUILD_FULL_VERSION_DIR%\search"
mkdir "%BUILD_FULL_VERSION_DIR%\llm"
mkdir "%BUILD_FULL_VERSION_DIR%\config"
mkdir "%BUILD_FULL_VERSION_DIR%\preprocessing"
mkdir "%BUILD_FULL_VERSION_DIR%\embeddings"
mkdir "%BUILD_FULL_VERSION_DIR%\vector_store"
mkdir "%BUILD_FULL_VERSION_DIR%\reranker"
mkdir "%BUILD_FULL_VERSION_DIR%\history"
mkdir "%BUILD_FULL_VERSION_DIR%\static"
mkdir "%BUILD_FULL_VERSION_DIR%\templates"
mkdir "%BUILD_FULL_VERSION_DIR%\Index"
mkdir "%BUILD_FULL_VERSION_DIR%\Archive"
mkdir "%BUILD_FULL_VERSION_DIR%\Service_manuals"
mkdir "%BUILD_FULL_VERSION_DIR%\kb"

:: 3. Copy modules
echo [*] Copying source code...
robocopy web "%BUILD_FULL_VERSION_DIR%\web" /E /NJH /NJS /NDL /NFL >nul
robocopy search "%BUILD_FULL_VERSION_DIR%\search" /E /NJH /NJS /NDL /NFL >nul
robocopy llm "%BUILD_FULL_VERSION_DIR%\llm" /E /NJH /NJS /NDL /NFL >nul
robocopy config "%BUILD_FULL_VERSION_DIR%\config" /E /NJH /NJS /NDL /NFL >nul
robocopy preprocessing "%BUILD_FULL_VERSION_DIR%\preprocessing" /E /NJH /NJS /NDL /NFL >nul
robocopy embeddings "%BUILD_FULL_VERSION_DIR%\embeddings" /E /NJH /NJS /NDL /NFL >nul
robocopy vector_store "%BUILD_FULL_VERSION_DIR%\vector_store" /E /NJH /NJS /NDL /NFL >nul
robocopy reranker "%BUILD_FULL_VERSION_DIR%\reranker" /E /NJH /NJS /NDL /NFL >nul
robocopy history "%BUILD_FULL_VERSION_DIR%\history" /E /NJH /NJS /NDL /NFL >nul
robocopy kb "%BUILD_FULL_VERSION_DIR%\kb" /E /NJH /NJS /NDL /NFL >nul

:: 4. Copy static resources and templates
echo [*] Copying static files and templates...
robocopy static "%BUILD_FULL_VERSION_DIR%\static" /E /NJH /NJS /NDL /NFL >nul
robocopy templates "%BUILD_FULL_VERSION_DIR%\templates" /E /NJH /NJS /NDL /NFL >nul
if exist images robocopy images "%BUILD_FULL_VERSION_DIR%\images" /E /NJH /NJS /NDL /NFL >nul

:: 5. Copy full (non-anonymized) knowledge base and index
echo [*] Copying full knowledge base and index...
robocopy Index "%BUILD_FULL_VERSION_DIR%\Index" /E /NJH /NJS /NDL /NFL >nul

:: 5.1 Copy all forum archives
echo [*] Copying all forum archives...
robocopy Archive "%BUILD_FULL_VERSION_DIR%\Archive" /E /NJH /NJS /NDL /NFL >nul

:: 6. Copy configurations and scripts
echo [*] Copying configs and index utilities...
copy .gitignore "%BUILD_FULL_VERSION_DIR%\" >nul
copy README.md "%BUILD_FULL_VERSION_DIR%\" >nul
copy related_models.json "%BUILD_FULL_VERSION_DIR%\" >nul
copy translations.json "%BUILD_FULL_VERSION_DIR%\" >nul
copy requirements.txt "%BUILD_FULL_VERSION_DIR%\" >nul
copy index_pdfs.py "%BUILD_FULL_VERSION_DIR%\" >nul
copy PDF_INDEXING_ONLY.bat "%BUILD_FULL_VERSION_DIR%\" >nul
if exist models_list.txt copy models_list.txt "%BUILD_FULL_VERSION_DIR%\" >nul
if exist settings.json copy settings.json "%BUILD_FULL_VERSION_DIR%\" >nul

:: 7. Create launcher script (start.bat) for Full
echo [*] Creating autorun file...
echo @echo off > "%BUILD_FULL_VERSION_DIR%\start.bat"
echo title KM Print Fix Hub v 1.20 (%CURRENT_DATE%) >> "%BUILD_FULL_VERSION_DIR%\start.bat"
echo echo [*] Starting KM Print Fix Hub backend server... >> "%BUILD_FULL_VERSION_DIR%\start.bat"
echo python web/app.py >> "%BUILD_FULL_VERSION_DIR%\start.bat"
echo pause >> "%BUILD_FULL_VERSION_DIR%\start.bat"

:: 8. Create readme file (README.txt) for Full
echo [*] Creating readme instruction file...
echo KM Print Fix Hub v 1.20 (%CURRENT_DATE%) > "%BUILD_FULL_VERSION_DIR%\README.txt"
echo ===================================== >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo [RU] РУССКАЯ ИНСТРУКЦИЯ / RUSSIAN GUIDE >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo --------------------------------------- >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo Система RAG-поиска и технической поддержки по оборудованию Konica Minolta. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo УСТАНОВКА И ЗАПУСК: >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 1. Установите Python 3.10 или новее. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 2. Откройте командную строку в этой папке и установите зависимости: >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo    pip install -r requirements.txt >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 3. Запустите сервер с помощью файла: >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo    start.bat >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 4. Откройте в браузере: http://127.0.0.1:8000/ >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo ДОБАВЛЕНИЕ СВОИХ PDF СЕРВИС-МАНУАЛОВ: >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo Для добавления собственных PDF мануалов поместите их в папку Service_manuals и запустите приложение (start.bat). >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo Для удаления PDF из индекса, удалите их из Service_manuals и Archive\official и перезапустите приложение. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo ПОДКЛЮЧЕНИЕ К LM STUDIO: >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 1. Запустите LM Studio. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 2. Скачайте и выберите модель. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo    Рекомендуемая модель: qwen/qwen3-4b-2507 >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 3. Перейдите во вкладку "Local Server" в LM Studio и запустите сервер (Start Server). >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 4. Порт сервера по умолчанию: http://localhost:1234 >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 5. Настройки RAG-сервера автоматически подключатся к LM Studio. Если вы изменили порт в LM Studio, перейдите в меню "Настройки" (Settings) в веб-интерфейсе KM Print Fix Hub и укажите актуальный "LM Studio API Base". >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo --------------------------------------- >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo [EN] ENGLISH GUIDE / АНГЛИЙСКАЯ ИНСТРУКЦИЯ >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo --------------------------------------- >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo RAG Search and Technical Support System for Konica Minolta Equipment. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo INSTALLATION AND RUNNING: >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 1. Install Python 3.10 or newer. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 2. Open a command prompt/terminal in this folder and install dependencies: >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo    pip install -r requirements.txt >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 3. Run the server using the file: >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo    start.bat >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 4. Open in browser: http://127.0.0.1:8000/ >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo ADDING YOUR OWN SERVICE MANUALS: >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo To add custom PDF manuals, place them in the Service_manuals folder and run start.bat. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo To remove PDFs from index, delete them from Service_manuals and Archive\official folders, then restart. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo CONNECTING TO LM STUDIO: >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 1. Start LM Studio. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 2. Download and select the model. >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo    Recommended model: qwen/qwen3-4b-2507 >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 3. Go to the "Local Server" tab in LM Studio and start the server (Start Server). >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 4. Default server port: http://localhost:1234 >> "%BUILD_FULL_VERSION_DIR%\README.txt"
echo 5. The RAG server settings will automatically connect to LM Studio. If you changed the port in LM Studio, go to the "Settings" menu in the KM Print Fix Hub web interface and specify the correct "LM Studio API Base". >> "%BUILD_FULL_VERSION_DIR%\README.txt"

echo.
echo [+] Full version build complete: "%BUILD_FULL_VERSION_DIR%"
echo.
pause
