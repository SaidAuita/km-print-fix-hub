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

app = FastAPI(title="KM Print Fix Hub v 1.00 (2026-07-07)")

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

# Автоматическое обновление индекса PDF при изменении файлов в папке Service_manuals
try:
    from index_pdfs import check_pdf_changes, run_pdf_update
    is_anon_build = os.path.exists(os.path.join(BASE_DIR, "Index_anon")) or "Index_anon" in config_mgr.get("INDEX_DIR", "")
    if check_pdf_changes():
        print("[*] Обнаружены изменения в PDF-руководствах. Запуск автоматического обновления индекса...")
        run_pdf_update(anonymize=is_anon_build)
except Exception as e:
    print(f"[!] Ошибка автоматической переиндексации PDF: {e}")

search_coordinator = SearchCoordinator()
llm_client = LLMClient()
history_mgr = HistoryManager(db_path=os.path.join(BASE_DIR, "history.db"))

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    history = history_mgr.get_history()
    settings = config_mgr.get_all()
    loaded_model = llm_client._get_loaded_model_name()
    
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

    def sse_generator():
        # 1. Сначала отправляем отладочную информацию по поиску (Debug)
        yield f"event: debug\ndata: {json.dumps(debug_info, ensure_ascii=False)}\n\n"
        
        # 2. Стримим ответ от LLM
        full_answer = ""
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

@app.post("/history/delete/{chat_id}")
async def delete_history_item(chat_id: int):
    history_mgr.delete_chat(chat_id)
    return {"status": "success", "message": f"Диалог #{chat_id} удален"}

@app.post("/history/clear")
async def clear_all_history():
    history_mgr.clear_history()
    return {"status": "success", "message": "История очищена"}

if __name__ == "__main__":
    import uvicorn
    host = config_mgr.get("WEB_HOST", "127.0.0.1")
    port = config_mgr.get("WEB_PORT", 8000)
    print(f"[*] Запуск сервера помощника на http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
