# web/app.py
# FastAPI сервер локального веб-приложения RAG-помощника.

import os
import sys

# Используем зеркало Hugging Face для надежной и быстрой загрузки моделей в РФ
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

import json
from fastapi import FastAPI, Request, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Добавляем корень проекта в пути импорта для избежания проблем
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.manager import ConfigManager
from search.coordinator import SearchCoordinator
from llm.client import LLMClient
from history.manager import HistoryManager

app = FastAPI(title="KM Print Fix Hub v1.20 Light")

# Настройка путей
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# Монтирование статики и архива форума
os.makedirs(os.path.join(BASE_DIR, "static"), exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Кастомный обработчик для правильной отдачи кодировки и пагинации в HTML-архиве форума
@app.get("/archive/{filepath:path}")
async def serve_archive_file(filepath: str, request: Request):
    import re
    # Разбираем путь для поиска локальных страниц обсуждений (пагинация)
    parts = filepath.split('/')
    if len(parts) >= 2:
        source_name = parts[0]
        thread_dir_name = parts[1]
        if thread_dir_name.startswith("thread_"):
            thread_dir = os.path.join(BASE_DIR, "Archive", source_name, thread_dir_name)
            
            # Проверяем vBulletin пагинацию (showthread.php?t=123&page=2)
            page = request.query_params.get("page")
            if page and page.isdigit():
                page_num = int(page)
                local_file = os.path.join(thread_dir, f"page{page_num:03d}.html")
                if os.path.exists(local_file):
                    with open(local_file, "rb") as f:
                        content = f.read()
                    # Определяем кодировку
                    charset = "windows-1251" if source_name in ["tradeprint", "colorprinting"] else "utf-8"
                    return Response(content=content, media_type=f"text/html; charset={charset}")
                    
            # Проверяем XenForo/другую пагинацию (page-2)
            match = re.search(r'page-(\d+)', filepath)
            if match:
                page_num = int(match.group(1))
                local_file = os.path.join(thread_dir, f"page{page_num:03d}.html")
                if os.path.exists(local_file):
                    with open(local_file, "rb") as f:
                        content = f.read()
                    charset = "windows-1251" if source_name in ["tradeprint", "colorprinting"] else "utf-8"
                    return Response(content=content, media_type=f"text/html; charset={charset}")

    file_path = os.path.join(BASE_DIR, "Archive", filepath)
    if not os.path.exists(file_path) or os.path.isdir(file_path):
        raise HTTPException(status_code=404, detail="Файл не найден")
    
    if filepath.endswith(".html") or filepath.endswith(".htm"):
        # Определяем кодировку
        charset = "windows-1251"
        for utf8_source in ["printplanet", "copytechnet"]:
            if filepath.startswith(utf8_source):
                charset = "utf-8"
                break
        with open(file_path, "rb") as f:
            content = f.read()
        return Response(content=content, media_type=f"text/html; charset={charset}")
        
    return FileResponse(file_path)

# Загрузка локализации интерфейса
TRANSLATIONS_FILE = os.path.join(BASE_DIR, "translations.json")
def load_translations():
    try:
        with open(TRANSLATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] Ошибка загрузки translations.json: {e}")
        return {"ru": {}}

translations = load_translations()

# Инициализация менеджеров
config_mgr = ConfigManager()



search_coordinator = SearchCoordinator()
llm_client = LLMClient()
history_mgr = HistoryManager(db_path=os.path.join(BASE_DIR, "history.db"))

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    history = history_mgr.get_history()
    settings = config_mgr.get_all()
    loaded_model = llm_client.get_model_name()
    
    lang = settings.get("LAST_LANG", "ru")
    t = translations.get(lang, translations.get("ru", {}))
    
    # Совместимость со старыми и новыми версиями Starlette/FastAPI:
    # В Starlette 0.28+ сигнатура: TemplateResponse(request, name, context)
    # В старых версиях: TemplateResponse(name, context) (где context должен содержать "request")
    import inspect
    sig = inspect.signature(templates.TemplateResponse)
    
    # Check if Archive folder has any subdirectories to determine is_build mode
    archive_path = os.path.join(BASE_DIR, "Archive")
    has_archive = False
    if os.path.exists(archive_path):
        try:
            # Only count actual forum subdirectories, ignore 'official' (manuals)
            forum_sources = {"tradeprint", "copytechnet", "printplanet", "colorprinting"}
            subdirs = [d for d in os.listdir(archive_path) if os.path.isdir(os.path.join(archive_path, d)) and d.lower() in forum_sources]
            if len(subdirs) > 0:
                has_archive = True
        except Exception:
            pass
    is_build = not has_archive

    # Load synchronization dates
    sync_dates = {}
    sync_dates_path = os.path.join(BASE_DIR, "Index", "sync_dates.json")
    if os.path.exists(sync_dates_path):
        try:
            with open(sync_dates_path, "r", encoding="utf-8") as f:
                sync_dates = json.load(f)
        except Exception:
            pass

    # Load list of official PDFs
    official_pdfs = []
    official_path = os.path.join(BASE_DIR, "Archive", "official")
    if os.path.exists(official_path):
        try:
            official_pdfs = sorted([f for f in os.listdir(official_path) if f.lower().endswith(".pdf")])
        except Exception:
            pass

    context = {
        "history": history,
        "settings": settings,
        "loaded_model": loaded_model,
        "t": t,
        "is_build": is_build,
        "sync_dates": sync_dates,
        "official_pdfs": official_pdfs,
        "available_languages": [{"code": code, "name": data.get("lang_name")} for code, data in translations.items()]
    }
    
    if "request" in sig.parameters:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context=context
        )
    else:
        context["request"] = request
        return templates.TemplateResponse(
            name="index.html",
            context=context
        )

@app.post("/ask")
async def ask_question(request: Request):
    data = await request.json()
    query = data.get("query", "").strip()
    model = data.get("model", "all")
    search_mode = data.get("search_mode", "all")
    strict_mode = data.get("strict_mode", False)
    show_reasoning = data.get("show_reasoning", False)
    source_filter = data.get("source_filter", "auto")
    enable_context_optimizer = data.get("enable_context_optimizer", False)
    
    if not query:
        raise HTTPException(status_code=400, detail="Запрос не может быть пустым")

    # Выставляем состояние оптимизатора контекста
    config_mgr.set("LAST_ENABLE_CONTEXT_OPTIMIZER", enable_context_optimizer)
    config_mgr.set("ENABLE_CONTEXT_OPTIMIZER", enable_context_optimizer)

    # Выполняем 3-ступенчатый поиск
    retrieved_docs, debug_info = search_coordinator.search(query, model=model, search_mode=search_mode, source_filter=source_filter)
    
    # Формируем промпт для LLM
    system_prompt, user_prompt, used_docs = llm_client.build_prompt(
        query, retrieved_docs, strict_mode=strict_mode, show_reasoning=show_reasoning
    )
    
    # Готовим лог источников для истории и фронтенда
    used_docs_log = []
    for idx, (doc, score) in enumerate(used_docs, 1):
        used_docs_log.append({
            "idx": idx,
            "id": doc["id"],
            "thread_id": doc["thread_id"],
            "title": doc["thread_title"],
            "url": doc["url"],
            "score": round(score, 4),
            "model": doc.get("model", "KM-General"),
            "source": doc.get("metadata", {}).get("source", "tradeprint"),
            "authors": doc.get("metadata", {}).get("authors", []),
            "posts": doc.get("metadata", {}).get("post_numbers", []),
            "page": doc.get("metadata", {}).get("page", 1),
            "document": doc.get("metadata", {}).get("document", "")
        })

    # Перевод названий тем форумов на язык интерфейса (опционально)
    translate_titles = config_mgr.get("TRANSLATE_THREAD_TITLES", True)
    target_lang = config_mgr.get("LAST_LANG", "ru")
    
    if translate_titles:
        unique_threads = {}
        for doc in used_docs_log:
            th_id = doc["thread_id"]
            if th_id and th_id != "official" and th_id not in unique_threads:
                unique_threads[th_id] = {
                    "title": doc["title"],
                    "source": doc["source"]
                }
        
        translated_titles = {}
        for th_id, th_info in unique_threads.items():
            orig_title = th_info["title"]
            source_lang = "ru" if th_info["source"] == "tradeprint" else "en"
            
            if source_lang != target_lang:
                try:
                    translated = llm_client.translate_text(orig_title, target_lang)
                    if translated and not translated.startswith("[Error translating text") and not translated.startswith("[!"):
                        translated_titles[th_id] = translated
                except Exception as e:
                    print(f"[!] Ошибка перевода названия темы '{orig_title}': {e}")
                    
        for doc in used_docs_log:
            th_id = doc["thread_id"]
            if th_id in translated_titles:
                doc["title"] = translated_titles[th_id]

    def sse_generator():
        # 1. Сначала отправляем отладочную информацию по поиску (Debug)
        yield f"event: debug\ndata: {json.dumps(debug_info, ensure_ascii=False)}\n\n"
        
        # 2. Стримим ответ от LLM или пишем, что анализ отключен
        context_mode = config_mgr.get("LLM_CONTEXT_MODE", "quality")
        full_answer = ""
        if context_mode == "off":
            lang = config_mgr.get("LAST_LANG", "ru")
            t = translations.get(lang, translations.get("ru", {}))
            msg = t.get("llm_analysis_disabled", "LLM analysis is disabled. Showing search results:")
            full_answer = msg
            yield f"data: {json.dumps({'text': msg}, ensure_ascii=False)}\n\n"
        else:
            for chunk in llm_client.generate_answer_stream(system_prompt, user_prompt):
                full_answer += chunk
                yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
            
        # 3. Сохраняем диалог в историю
        if full_answer and not full_answer.startswith("\n[!] Ошибка"):
            history_mgr.add_chat(query, full_answer, used_docs_log)
            
        # 4. В самом конце отправляем источники
        yield f"event: sources\ndata: {json.dumps(used_docs_log, ensure_ascii=False)}\n\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")

@app.get("/chunk/{chunk_id}")
async def get_chunk_details(chunk_id: str):
    chunk = search_coordinator.fts_searcher.get_chunk(chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Фрагмент не найден")
    return JSONResponse(chunk)

@app.get("/chunk/navigate/{chunk_id}")
async def navigate_chunk_details(chunk_id: str, direction: str = "next", page: int = None):
    chunk = search_coordinator.fts_searcher.get_chunk_by_navigation(chunk_id, direction, page)
    if not chunk:
        raise HTTPException(status_code=404, detail="Фрагмент не найден")
    return JSONResponse(chunk)

@app.post("/translate")
async def translate_chunk(request: Request):
    data = await request.json()
    text = data.get("text", "").strip()
    target_lang = data.get("target_lang", "ru").strip()
    
    if not text:
        raise HTTPException(status_code=400, detail="Текст для перевода пуст")
        
    print(f"[*] Requesting translation of chunk to: {target_lang}")
    translated = llm_client.translate_text(text, target_lang)
    print(f"[*] LLM returned translation length: {len(translated)}")
    return {"translated": translated}

@app.post("/settings")
async def update_settings(settings: dict):
    for k, v in settings.items():
        config_mgr.set(k, v)
    if config_mgr.save():
        return {"status": "success", "message": "Настройки успешно сохранены"}
    raise HTTPException(status_code=500, detail="Не удалось сохранить настройки в файл")

@app.get("/api/models")
async def get_available_models(provider: str = None, api_base: str = None):
    """
    Returns a list of all available models from the specified or active LLM provider.
    """
    if not provider:
        provider = config_mgr.get("LLM_PROVIDER", "lmstudio")
    if not api_base:
        if provider == "ollama":
            api_base = config_mgr.get("OLLAMA_API_BASE", "http://localhost:11434/v1")
        else:
            api_base = config_mgr.get("LM_STUDIO_API_BASE", "http://localhost:1234/v1")
            
    # Ensure Ollama has the /v1 prefix for listing models if it points to native port
    if provider == "ollama":
        if not api_base.endswith("/v1") and not api_base.endswith("/v1/"):
            api_base = f"{api_base.rstrip('/')}/v1"
            
    models_url = f"{api_base.rstrip('/')}/models"
    try:
        import requests
        response = requests.get(models_url, timeout=10.0)
        if response.status_code == 200:
            data = response.json()
            models = data.get("data", [])
            return {"models": [m.get("id") for m in models]}
    except Exception as e:
        print(f"[!] Error fetching models list from {models_url}: {e}")
        
    return {"models": []}

@app.post("/history/delete/{chat_id}")
async def delete_history_item(chat_id: int):
    history_mgr.delete_chat(chat_id)
    return {"status": "success", "message": f"Диалог #{chat_id} удален"}

@app.post("/history/clear")
async def clear_all_history():
    history_mgr.clear_history()
    return {"status": "success", "message": "История очищена"}

# --- Machine Knowledge Base Endpoints ---
from fastapi import UploadFile, File
from kb.manager import KBManager
import shutil

kb_mgr = KBManager(data_dir=os.path.join(BASE_DIR, "kb_data"))

@app.middleware("http")
async def db_sync_middleware(request: Request, call_next):
    if request.url.path.startswith("/kb"):
        kb_mgr.load_last_active_db()
    response = await call_next(request)
    return response

@app.get("/kb", response_class=HTMLResponse)
async def serve_kb(request: Request):
    settings = config_mgr.get_all()
    lang = settings.get("LAST_LANG", "ru")
    t = translations.get(lang, translations.get("ru", {}))
    
    # TemplateResponse compatibility check
    import inspect
    sig = inspect.signature(templates.TemplateResponse)
    
    context = {
        "request": request,
        "t": t,
        "active_db": kb_mgr.active_db_name[:-3] if kb_mgr.active_db_name else None,
        "databases": kb_mgr.list_databases(),
        "lang_code": lang,
        "available_languages": [{"code": code, "name": data.get("lang_name")} for code, data in translations.items()]
    }
    
    if "request" in sig.parameters:
        return templates.TemplateResponse(
            request=request,
            name="kb.html",
            context=context
        )
    else:
        context["request"] = request
        return templates.TemplateResponse(
            name="kb.html",
            context=context
        )

# DB Management API
@app.get("/kb/api/databases")
async def kb_list_dbs():
    return {
        "databases": kb_mgr.list_databases(),
        "active_db": kb_mgr.active_db_name[:-3] if kb_mgr.active_db_name else None
    }

@app.post("/kb/api/databases")
async def kb_manage_db(payload: dict):
    action = payload.get("action")
    name = payload.get("name", "").strip()
    
    if action == "create":
        if not name:
            raise HTTPException(status_code=400, detail="Имя базы данных пустое")
        try:
            filename = kb_mgr.create_database(name)
            return {"status": "success", "db": filename[:-3]}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
            
    elif action == "switch":
        if not name:
            raise HTTPException(status_code=400, detail="Имя базы данных пустое")
        try:
            kb_mgr.set_active_db(name)
            return {"status": "success", "db": kb_mgr.active_db_name[:-3]}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
            
    elif action == "delete":
        if not name:
            raise HTTPException(status_code=400, detail="Имя базы данных пустое")
        try:
            kb_mgr.delete_database(name)
            return {"status": "success"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
            
    elif action == "rename":
        new_name = payload.get("new_name", "").strip()
        if not name or not new_name:
            raise HTTPException(status_code=400, detail="Имя базы данных пустое")
        try:
            filename = kb_mgr.rename_database(name, new_name)
            return {"status": "success", "db": filename[:-3]}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
            
    elif action == "close":
        try:
            kb_mgr.active_db_name = None
            kb_mgr.active_db_path = None
            kb_mgr.save_last_active_db()
            return {"status": "success"}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
            
    raise HTTPException(status_code=400, detail="Неверное действие")

# Upload Attachments
@app.post("/kb/api/upload")
async def kb_upload_file(file: UploadFile = File(...)):
    if not kb_mgr.active_db_name:
        raise HTTPException(status_code=400, detail="Нет активной базы данных")
    
    db_base = kb_mgr.active_db_name[:-3]
    att_dir = os.path.join(kb_mgr.data_dir, "attachments", db_base)
    os.makedirs(att_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_filename = os.path.basename(file.filename)
    filename = f"{timestamp}_{raw_filename}"
    # Deduplicate filename if already exists
    base, ext = os.path.splitext(filename)
    counter = 1
    target_path = os.path.join(att_dir, filename)
    while os.path.exists(target_path):
        filename = f"{base}_{counter}{ext}"
        target_path = os.path.join(att_dir, filename)
        counter += 1
        
    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {"status": "success", "filename": filename, "url": f"/kb/attachments/{filename}"}

@app.get("/kb/attachments/{filename}")
async def kb_serve_attachment(filename: str):
    if not kb_mgr.active_db_name:
        raise HTTPException(status_code=400, detail="Нет активной базы данных")
    db_base = kb_mgr.active_db_name[:-3]
    file_path = os.path.join(kb_mgr.data_dir, "attachments", db_base, os.path.basename(filename))
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Файл не найден")
    return FileResponse(file_path)

# Solutions CRUD API
@app.get("/kb/api/solutions")
async def get_solutions():
    if not kb_mgr.active_db_name:
        return []
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM solutions ORDER BY date DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/kb/api/solutions")
async def create_solution(payload: dict):
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    
    sql = """
        INSERT INTO solutions (title, machine, serial_number, symptom, cause, solution, actions, result, date, author, tags, forum_links, manual_links, photos, attachments)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    cursor.execute(sql, (
        payload.get("title"),
        payload.get("machine"),
        payload.get("serial_number"),
        payload.get("symptom"),
        payload.get("cause"),
        payload.get("solution"),
        payload.get("actions"),
        payload.get("result"),
        payload.get("date", datetime.now().strftime("%Y-%m-%d")),
        payload.get("author"),
        payload.get("tags"),
        json.dumps(payload.get("forum_links", [])),
        json.dumps(payload.get("manual_links", [])),
        json.dumps(payload.get("photos", [])),
        json.dumps(payload.get("attachments", []))
    ))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"status": "success", "id": new_id}

def delete_file_if_exists(filename):
    if not kb_mgr.active_db_name:
        return
    db_base = kb_mgr.active_db_name[:-3]
    file_path = os.path.join(kb_mgr.data_dir, "attachments", db_base, os.path.basename(filename))
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass

@app.put("/kb/api/solutions/{item_id}")
async def update_solution(item_id: int, payload: dict):
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    
    # Fetch old files first to find removed attachments
    cursor.execute("SELECT photos, attachments FROM solutions WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    old_photos = []
    old_files = []
    if row:
        try:
            old_photos = json.loads(row["photos"] or "[]")
            old_files = json.loads(row["attachments"] or "[]")
        except Exception:
            pass
            
    new_photos = payload.get("photos", [])
    new_files = payload.get("attachments", [])
    
    removed_photos = set(old_photos) - set(new_photos)
    removed_files = set(old_files) - set(new_files)
    
    for filename in removed_photos.union(removed_files):
        delete_file_if_exists(filename)
        
    sql = """
        UPDATE solutions 
        SET title=?, machine=?, serial_number=?, symptom=?, cause=?, solution=?, actions=?, result=?, date=?, author=?, tags=?, forum_links=?, manual_links=?, photos=?, attachments=?
        WHERE id=?
    """
    cursor.execute(sql, (
        payload.get("title"),
        payload.get("machine"),
        payload.get("serial_number"),
        payload.get("symptom"),
        payload.get("cause"),
        payload.get("solution"),
        payload.get("actions"),
        payload.get("result"),
        payload.get("date"),
        payload.get("author"),
        payload.get("tags"),
        json.dumps(payload.get("forum_links", [])),
        json.dumps(payload.get("manual_links", [])),
        json.dumps(payload.get("photos", [])),
        json.dumps(payload.get("attachments", [])),
        item_id
    ))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/kb/api/solutions/{item_id}")
async def delete_solution(item_id: int):
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    
    # Fetch record to find files to delete
    cursor.execute("SELECT photos, attachments FROM solutions WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    if row:
        try:
            photos = json.loads(row["photos"] or "[]")
            files = json.loads(row["attachments"] or "[]")
            for filename in photos + files:
                delete_file_if_exists(filename)
        except Exception:
            pass
            
    cursor.execute("DELETE FROM solutions WHERE id = ?", (item_id,))
    cursor.execute("DELETE FROM related_records WHERE (record_type_a = 'solution' AND record_id_a = ?) OR (record_type_b = 'solution' AND record_id_b = ?)", (item_id, item_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

# Maintenance CRUD API
@app.get("/kb/api/maintenance")
async def get_maintenance():
    if not kb_mgr.active_db_name:
        return []
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM maintenance_history ORDER BY date DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/kb/api/maintenance")
async def create_maintenance(payload: dict):
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    sql = """
        INSERT INTO maintenance_history (type, title, date, counter, performer, comments, photos, cost)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    cursor.execute(sql, (
        payload.get("type"),
        payload.get("title"),
        payload.get("date", datetime.now().strftime("%Y-%m-%d")),
        payload.get("counter"),
        payload.get("performer"),
        payload.get("comments"),
        json.dumps(payload.get("photos", [])),
        payload.get("cost")
    ))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"status": "success", "id": new_id}

@app.put("/kb/api/maintenance/{item_id}")
async def update_maintenance(item_id: int, payload: dict):
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    
    # Fetch old record first to find deleted photos
    cursor.execute("SELECT photos FROM maintenance_history WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    old_photos = []
    if row:
        try:
            old_photos = json.loads(row["photos"] or "[]")
        except Exception:
            pass
            
    new_photos = payload.get("photos", [])
    removed_photos = set(old_photos) - set(new_photos)
    for filename in removed_photos:
        delete_file_if_exists(filename)
        
    sql = """
        UPDATE maintenance_history 
        SET type=?, title=?, date=?, counter=?, performer=?, comments=?, photos=?, cost=?
        WHERE id=?
    """
    cursor.execute(sql, (
        payload.get("type"),
        payload.get("title"),
        payload.get("date"),
        payload.get("counter"),
        payload.get("performer"),
        payload.get("comments"),
        json.dumps(payload.get("photos", [])),
        payload.get("cost"),
        item_id
    ))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/kb/api/maintenance/{item_id}")
async def delete_maintenance(item_id: int):
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    
    # Fetch record first to find photos to delete
    cursor.execute("SELECT photos FROM maintenance_history WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    if row:
        try:
            photos = json.loads(row["photos"] or "[]")
            for filename in photos:
                delete_file_if_exists(filename)
        except Exception:
            pass
            
    cursor.execute("DELETE FROM maintenance_history WHERE id = ?", (item_id,))
    cursor.execute("DELETE FROM related_records WHERE (record_type_a = 'maintenance' AND record_id_a = ?) OR (record_type_b = 'maintenance' AND record_id_b = ?)", (item_id, item_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

# Parts CRUD API
@app.get("/kb/api/parts")
async def get_parts():
    if not kb_mgr.active_db_name:
        return []
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM installed_parts ORDER BY date_installed DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/kb/api/parts")
async def create_part(payload: dict):
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    sql = """
        INSERT INTO installed_parts (part_name, date_installed, date_removed, resource_limit, current_counter, comments)
        VALUES (?, ?, ?, ?, ?, ?)
    """
    cursor.execute(sql, (
        payload.get("part_name"),
        payload.get("date_installed", datetime.now().strftime("%Y-%m-%d")),
        payload.get("date_removed"),
        payload.get("resource_limit"),
        payload.get("current_counter"),
        payload.get("comments")
    ))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"status": "success", "id": new_id}

@app.put("/kb/api/parts/{item_id}")
async def update_part(item_id: int, payload: dict):
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    sql = """
        UPDATE installed_parts 
        SET part_name=?, date_installed=?, date_removed=?, resource_limit=?, current_counter=?, comments=?
        WHERE id=?
    """
    cursor.execute(sql, (
        payload.get("part_name"),
        payload.get("date_installed"),
        payload.get("date_removed"),
        payload.get("resource_limit"),
        payload.get("current_counter"),
        payload.get("comments"),
        item_id
    ))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/kb/api/parts/{item_id}")
async def delete_part(item_id: int):
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM installed_parts WHERE id = ?", (item_id,))
    cursor.execute("DELETE FROM related_records WHERE (record_type_a = 'part' AND record_id_a = ?) OR (record_type_b = 'part' AND record_id_b = ?)", (item_id, item_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

# Instructions CRUD API
@app.get("/kb/api/instructions")
async def get_instructions():
    if not kb_mgr.active_db_name:
        return []
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_instructions ORDER BY date_created DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/kb/api/instructions")
async def create_instruction(payload: dict):
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    sql = """
        INSERT INTO user_instructions (title, content, date_created, tags)
        VALUES (?, ?, ?, ?)
    """
    cursor.execute(sql, (
        payload.get("title"),
        payload.get("content"),
        payload.get("date_created", datetime.now().strftime("%Y-%m-%d")),
        payload.get("tags")
    ))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return {"status": "success", "id": new_id}

@app.put("/kb/api/instructions/{item_id}")
async def update_instruction(item_id: int, payload: dict):
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    sql = """
        UPDATE user_instructions 
        SET title=?, content=?, date_created=?, tags=?
        WHERE id=?
    """
    cursor.execute(sql, (
        payload.get("title"),
        payload.get("content"),
        payload.get("date_created"),
        payload.get("tags"),
        item_id
    ))
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.delete("/kb/api/instructions/{item_id}")
async def delete_instruction(item_id: int):
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_instructions WHERE id = ?", (item_id,))
    cursor.execute("DELETE FROM related_records WHERE (record_type_a = 'instruction' AND record_id_a = ?) OR (record_type_b = 'instruction' AND record_id_b = ?)", (item_id, item_id))
    conn.commit()
    conn.close()
    return {"status": "success"}

# Relations API
@app.get("/kb/api/relations")
async def get_relations(type: str, id: int):
    if not kb_mgr.active_db_name:
        return []
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    sql = """
        SELECT id, record_type_a, record_id_a, record_type_b, record_id_b 
        FROM related_records 
        WHERE (record_type_a = ? AND record_id_a = ?) 
           OR (record_type_b = ? AND record_id_b = ?)
    """
    cursor.execute(sql, (type, id, type, id))
    rows = cursor.fetchall()
    
    results = []
    for r in rows:
        other_type = r["record_type_b"] if r["record_type_a"] == type and r["record_id_a"] == id else r["record_type_a"]
        other_id = r["record_id_b"] if r["record_type_a"] == type and r["record_id_a"] == id else r["record_id_a"]
        
        other_title = "Unknown"
        if other_type == "solution":
            cursor.execute("SELECT title FROM solutions WHERE id = ?", (other_id,))
        elif other_type == "maintenance":
            cursor.execute("SELECT coalesce(title, type) FROM maintenance_history WHERE id = ?", (other_id,))
        elif other_type == "part":
            cursor.execute("SELECT part_name FROM installed_parts WHERE id = ?", (other_id,))
        elif other_type == "instruction":
            cursor.execute("SELECT title FROM user_instructions WHERE id = ?", (other_id,))
            
        row = cursor.fetchone()
        if row:
            other_title = row[0]
            
        results.append({
            "relation_id": r["id"],
            "type": other_type,
            "id": other_id,
            "title": other_title
        })
        
    conn.close()
    return results

@app.post("/kb/api/relations")
async def link_records(payload: dict):
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    
    type_a = payload.get("type_a")
    id_a = payload.get("id_a")
    type_b = payload.get("type_b")
    id_b = payload.get("id_b")
    
    if (type_a, id_a) > (type_b, id_b):
        type_a, id_a, type_b, id_b = type_b, id_b, type_a, id_a
        
    try:
        cursor.execute(
            "INSERT INTO related_records (record_type_a, record_id_a, record_type_b, record_id_b) VALUES (?, ?, ?, ?)",
            (type_a, id_a, type_b, id_b)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()
    return {"status": "success"}

@app.delete("/kb/api/relations/{relation_id}")
async def unlink_records(relation_id: int):
    conn = kb_mgr.get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM related_records WHERE id = ?", (relation_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}

# Instant Search
@app.get("/kb/api/search")
async def kb_search(q: str):
    if not kb_mgr.active_db_name:
        return []
    return kb_mgr.search_kb(q)

# Backup and Restores
@app.get("/kb/api/backup/create")
async def kb_create_backup():
    try:
        filename = kb_mgr.create_backup()
        return {"status": "success", "filename": filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/kb/api/backup/download/{filename}")
async def kb_download_backup(filename: str):
    filepath = os.path.join(kb_mgr.backup_dir, os.path.basename(filename))
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Файл резервной копии не найден")
    return FileResponse(filepath, filename=filename, media_type="application/zip")

@app.post("/kb/api/backup/restore")
async def kb_restore_backup(file: UploadFile = File(...)):
    temp_path = os.path.join(kb_mgr.data_dir, "temp_restore.zip")
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        restored_db = kb_mgr.restore_backup(temp_path)
        return {"status": "success", "db": restored_db[:-3]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.get("/kb/api/export")
async def kb_export_data():
    if not kb_mgr.active_db_name:
        raise HTTPException(status_code=400, detail="Нет активной базы данных")
    data = kb_mgr.export_to_json()
    return JSONResponse(data)

@app.post("/kb/api/import")
async def kb_import_data(payload: dict):
    if not kb_mgr.active_db_name:
        raise HTTPException(status_code=400, detail="Нет активной базы данных")
    try:
        kb_mgr.import_from_json(payload)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/db/stats")
async def get_db_stats():
    import sqlite3
    fts_searcher = search_coordinator.fts_searcher
    if not fts_searcher or not fts_searcher.is_ready:
        return {"total_chunks": 0, "summarized_chunks": 0}
    try:
        conn = sqlite3.connect(fts_searcher.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM chunks")
        total_chunks = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM chunks WHERE summary IS NOT NULL AND summary != ''")
        summarized_chunks = cursor.fetchone()[0]
        conn.close()
        return {
            "total_chunks": total_chunks,
            "summarized_chunks": summarized_chunks
        }
    except Exception as e:
        print(f"[!] Error reading db stats: {e}")
        return {"total_chunks": 0, "summarized_chunks": 0}

from datetime import datetime

if __name__ == "__main__":
    import uvicorn
    host = config_mgr.get("WEB_HOST", "127.0.0.1")
    port = config_mgr.get("WEB_PORT", 8000)
    print(f"[*] Запуск сервера помощника на http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
