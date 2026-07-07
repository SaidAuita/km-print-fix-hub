# Инструкция по добавлению и индексации сервис-мануалов PDF
# Guide to Adding and Indexing PDF Service Manuals

---

## [RU] РУССКАЯ ИНСТРУКЦИЯ

### Как работает система хранения и индексации PDF
Для предотвращения случайного удаления документов и экономии места на диске в системе реализована следующая логика:
1. Вы кладете новые файлы PDF в рабочую папку `Service_manuals/`.
2. При запуске скрипта индексации `index_kb.py` файлы автоматически копируются (или обновляются) в папку `Archive/official/` (постоянное хранилище архива).
3. Индексатор парсит и нарезает на чанки PDF-файлы непосредственно из папки постоянного хранилища `Archive/official/`.
4. **После завершения индексации вы можете свободно удалять файлы из папки `Service_manuals/`** — документы останутся в базе знаний, так как они были скопированы в архив.

### Пошаговая инструкция по переиндексации
1. Поместите нужные файлы PDF в папку `Service_manuals/` в корне проекта.
2. Откройте консоль/терминал в корне проекта и запустите переиндексацию:
   ```bash
   python index_kb.py
   ```
   *Если вы хотите запустить быструю проверку без генерации полноценных эмбеддингов, используйте фиктивный провайдер:*
   ```bash
   python index_kb.py --provider mock
   ```
3. После завершения работы скрипта новые документы появятся в базе знаний. Вы можете удалить исходные PDF из папки `Service_manuals/`.
4. Соберите обновленную версию дистрибутива в папку `Build/`:
   ```bash
   build.bat
   ```

---

## [EN] ENGLISH GUIDE

### How PDF Storage and Indexing Works
To prevent accidental document loss and save workspace disk space, the system uses the following logic:
1. You place new PDF manuals in the working directory `Service_manuals/`.
2. When you run the indexing script `index_kb.py`, the files are automatically copied (or updated) to `Archive/official/` (the persistent archive storage).
3. The indexer parses and chunks the PDF files directly from the persistent archive folder `Archive/official/`.
4. **After indexing is complete, you can safely delete the files from the `Service_manuals/` directory** — the documents will remain in the knowledge base because they have been copied to the archive.

### Step-by-Step Indexing Instructions
1. Place the required PDF files in the `Service_manuals/` folder in the project root.
2. Open a console/terminal in the project root and run the indexing script:
   ```bash
   python index_kb.py
   ```
   *If you want to run a quick pipeline check without generating full embeddings, use the mock provider:*
   ```bash
   python index_kb.py --provider mock
   ```
3. Once the script finishes, the new documents will be active in the knowledge base. You can delete the source PDFs from the `Service_manuals/` folder.
4. Pack the updated version of the distribution into the `Build/` folder:
   ```bash
   build.bat
   ```
