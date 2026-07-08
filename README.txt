KM Print Fix Hub v 1.00 (2026-07-08) 
===================================== 
 
[RU] РУССКАЯ ИНСТРУКЦИЯ / RUSSIAN GUIDE 
--------------------------------------- 
Система RAG-поиска и технической поддержки по оборудованию Konica Minolta. 
 
УСТАНОВКА И ЗАПУСК: 
1. Установите Python 3.10 или новее. 
2. Откройте командную строку в этой папке и установите зависимости: 
   pip install -r requirements.txt 
3. Запустите сервер с помощью файла: 
   start.bat 
4. Откройте в браузере: http://127.0.0.1:8000/ 
 
ДОБАВЛЕНИЕ СВОИХ PDF СЕРВИС-МАНУАЛОВ: 
Для добавления собственных PDF мануалов поместите их в папку Service_manuals и запустите приложение (start.bat). 
Для удаления PDF из индекса, удалите их из Service_manuals и Archive\official и перезапустите приложение. 
 
ПОДКЛЮЧЕНИЕ К LM STUDIO: 
1. Запустите LM Studio. 
2. Скачайте и выберите модель. 
   Рекомендуемая модель: qwen/qwen3-4b-2507 
3. Перейдите во вкладку "Local Server" в LM Studio и запустите сервер (Start Server). 
4. Порт сервера по умолчанию: http://localhost:1234 
5. Настройки RAG-сервера автоматически подключатся к LM Studio. Если вы изменили порт в LM Studio, перейдите в меню "Настройки" (Settings) в веб-интерфейсе KM Print Fix Hub и укажите актуальный "LM Studio API Base". 
 
--------------------------------------- 
 
[EN] ENGLISH GUIDE / АНГЛИЙСКАЯ ИНСТРУКЦИЯ 
--------------------------------------- 
RAG Search and Technical Support System for Konica Minolta Equipment. 
 
INSTALLATION AND RUNNING: 
1. Install Python 3.10 or newer. 
2. Open a command prompt/terminal in this folder and install dependencies: 
   pip install -r requirements.txt 
3. Run the server using the file: 
   start.bat 
4. Open in browser: http://127.0.0.1:8000/ 
 
ADDING YOUR OWN SERVICE MANUALS: 
To add custom PDF manuals, place them in the Service_manuals folder and run start.bat. 
To remove PDFs from index, delete them from Service_manuals and Archive\official folders, then restart. 
 
CONNECTING TO LM STUDIO: 
1. Start LM Studio. 
2. Download and select the model. 
   Recommended model: qwen/qwen3-4b-2507 
3. Go to the "Local Server" tab in LM Studio and start the server (Start Server). 
4. Default server port: http://localhost:1234 
5. The RAG server settings will automatically connect to LM Studio. If you changed the port in LM Studio, go to the "Settings" menu in the KM Print Fix Hub web interface and specify the correct "LM Studio API Base". 
