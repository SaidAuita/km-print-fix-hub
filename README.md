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
   * **[Mega.nz Link for Light/Anonymized Index (Index_anon.zip)](https://mega.nz/)** (Placeholder)
2. Extract the index contents into the `Index/` folder in the project root.

#### 4. Launching the App
Run the startup script:
```bash
start.bat
```
Open your browser and navigate to: `http://127.0.0.1:8000/`

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
   * **[Ссылка на Mega.nz для Light (обезличенный индекс) (Index_anon.zip)](https://mega.nz/)** (Плейсхолдер)
2. Распакуйте содержимое архива индексов в папку `Index/` в корне проекта.

#### 4. Запуск приложения
Запустите стартовый файл:
```bash
start.bat
```
Откройте в браузере: `http://127.0.0.1:8000/`
