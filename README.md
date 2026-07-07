# KM Print Fix Hub

Bilingual documentation / Двуязычная документация: **[English](#english) | [Русский](#русский)**

---

## English

RAG (Retrieval-Augmented Generation) search engine and interactive technical support system for Konica Minolta production printers and copiers.

### 🌟 Features
* **Semantic & Keyword Search**: Combined BM25 (SQLite FTS5) and dense vector search (FAISS) for precise troubleshooting matching.
* **LLM Context Optimizer**: Custom pipeline to merge overlapping threads, strip duplicated quote blocks, and filter out conversational noise, saving up to 70% of LLM token context size.
* **Official Manuals & Forums**: Serves official PDF service manuals (directing to the exact page) and technical forum archives (TradePrint, CopyTechNet, PrintPlanet, ColorPrinting).
* **Multi-Language Support**: Complete interface translation in 10 languages and bilingual query translation (queries in any language are matched against English and Russian databases).
* **Anonymization Engine**: Light version replaces posters' names with generic identifiers to maintain privacy.

---

### 💻 Installation & Setup

#### 1. Setup LM Studio (LLM Provider)
1. Install [LM Studio](https://lmstudio.ai/).
2. Search and download the recommended model: `qwen/qwen3-4b-2507`.
3. In the "Local Server" tab, select the model and click **Start Server**.
4. > [!IMPORTANT]
   > Ensure that the **Context Length** in LM Studio is set to **20,000** or higher to accommodate RAG search matches.

#### 2. Install Python & Dependencies
1. Install Python 3.10 or newer.
2. Clone the repository code and install requirements:
   ```bash
   pip install -r requirements.txt
   ```

#### 3. Database Download (Mega.nz)
Since database indices are large, they are hosted externally.
1. Download the required database ZIP:
   * **[Mega.nz Link for Light/Anonymized Index (Index_anon.zip)](https://mega.nz/file/Oh52lJaT#e8kGp7mMv-71iP6GZdN3N7XS0bUVuFT_miDUbYBDMWw)**
2. Extract the index contents into the `Index/` folder in the project root.

#### 4. Launching the App
Run the startup script:
```bash
start.bat
```
Open your browser and navigate to: `http://127.0.0.1:8000/`

#### 5. Indexing Your Own PDF Manuals
The application supports automatic PDF indexing on startup:
1. Place your PDF files into the `Service_manuals/` directory in the project root.
2. Launch the application (`start.bat`). The server will automatically detect any new, updated, or deleted files, update the database, and rebuild the vector store.
3. If you need to remove PDF files from the index, delete them from the `Service_manuals/` and `Archive/official/` directories and restart the application. The index will rebuild and remove their data from the database.

---

## Русский

Поисковая RAG-система и интерактивный помощник технической поддержки по производительным печатным машинам и копирам Konica Minolta.

### 🌟 Возможности системы
* **Гибридный поиск**: Сочетание полнотекстового поиска FTS5 и векторной семантики (FAISS) для точного нахождения решений.
* **LLM Context Optimizer**: Интеллектуальный оптимизатор контекста, сжимающий его на 40-70% благодаря удалению цитат, склейке сообщений из одной ветки и фильтрации разговоров.
* **База знаний и PDF**: Индексация сервис-мануалов (с переходом на нужную страницу) и постов из 4 крупнейших форумов (TradePrint, CopyTechNet, PrintPlanet, ColorPrinting).
* **Многоязычность**: Локализация интерфейса на 10 языков и автоматический перевод поисковых запросов.
* **Анонимизация данных**: Light-версия заменяет реальные имена пользователей на порядковые маркеры для конфиденциальности.

---

### 💻 Установка и запуск

#### 1. Настройка LM Studio (Локальная LLM)
1. Установите [LM Studio](https://lmstudio.ai/).
2. Скачайте и выберите рекомендованную модель: `qwen/qwen3-4b-2507`.
3. Перейдите во вкладку "Local Server" и нажмите **Start Server**.
4. > [!IMPORTANT]
   > Обязательно выставите параметр **Context Length** (Размер контекста) в LM Studio на значение **20 000** или более.

#### 2. Установка Python и зависимостей
1. Установите Python 3.10 или новее.
2. Клонируйте код проекта и установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

#### 3. Загрузка базы данных (Mega.nz)
Файлы индексов базы знаний имеют большой объем и скачиваются отдельно.
1. Скачайте необходимый архив базы данных:
   * **[Ссылка на Mega.nz для Light (обезличенный индекс) (Index_anon.zip)](https://mega.nz/file/Oh52lJaT#e8kGp7mMv-71iP6GZdN3N7XS0bUVuFT_miDUbYBDMWw)**
2. Распакуйте содержимое архива индексов в папку `Index/` в корне проекта.

#### 4. Запуск приложения
Запустите стартовый файл:
```bash
start.bat
```
Откройте в браузере: `http://127.0.0.1:8000/`

#### 5. Индексирование собственных PDF-руководств
Приложение поддерживает автоматическое индексирование PDF при запуске:
1. Поместите ваши файлы PDF в папку `Service_manuals/` в корне проекта.
2. Запустите приложение (`start.bat`). Сервер автоматически обнаружит добавленные, измененные или удаленные файлы, обновит базу данных и перестроит векторный индекс.
3. Если нужно удалить из индекса файлы PDF — удалите их из папок `Service_manuals` и `Archive\official` и перезапустите приложение. Индекс перестроится и удалит информацию из базы.

---

### ☕ Support the Project / Поддержка проекта
If you find this project useful, you can support its development:  
Если проект оказался вам полезен, вы можете поддержать его разработку:
* **USDT (TRC20)**: `TBWzmMZWbirvACAtPfoZioAhhwSM4n2ArY`

---

### 🛠️ Other Projects / Мои проекты
* **[ComfyUI Photoshop Plugin (PH-CU-S)](https://github.com/SaidAuita/ComfyUI_PH-CU-S)**:
  A powerful Photoshop plugin powered by ComfyUI, providing direct integration with local generative models without any clouds, subscriptions, or recurring fees.  
  Мощный плагин для Photoshop на базе ComfyUI, обеспечивающий прямую интеграцию с локальными генеративными моделями без облаков, подписок и регулярных платежей.
