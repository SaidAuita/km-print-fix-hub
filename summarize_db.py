# summarize_db.py
# Скрипт для инкрементального технического сжатия чанков в базе данных.
# Поддерживает многопоточность для ускорения обработки на GPU или мощных CPU.

import os
import sys
import sqlite3
import json
import requests
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

# Добавляем корень проекта в пути импорта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.manager import ConfigManager
from llm.client import LLMClient

def process_chunk(row, api_url, model_name, provider):
    import time
    start_time = time.time()
    chunk_id, text, thread_title = row
    
    # Строим промпт для сжатия с жестким запретом на рассуждения (CoT)
    prompt = (
        "Сделай краткую техническую выжимку из этого обсуждения или документа о Konica Minolta на русском языке.\n"
        "Выдели только суть в строго следующем формате:\n"
        "Проблема: <коротко суть проблемы>\n"
        "Причина: <возможные причины, если упомянуты, иначе оставить пустым>\n"
        "Решение: <способы решения, если указаны, иначе оставить пустым>\n"
        "Модели: <конкретные модели принтеров, если упомянуты, иначе оставить пустым>\n\n"
        "ВАЖНО: Пиши СТРОГО только результат в указанном выше формате! "
        "Категорически запрещено выводить любые предварительные рассуждения, размышления вслух, "
        "пошаговый анализ или блок мыслей (Chain of Thought / <thought>).\n\n"
        f"Текст для сжатия:\n{text}"
    )

    payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 800,
        "stream": False
    }

    if provider == "ollama":
        payload["options"] = {
            "num_ctx": 4096  # Для сжатия одного чанка 4096 токенов более чем достаточно
        }

    try:
        response = requests.post(api_url, json=payload, timeout=90.0)
        response.raise_for_status()
        
        # Безопасное декодирование UTF-8 для предотвращения проблем с кодировкой
        data = json.loads(response.content.decode('utf-8'))
        summary = data["choices"][0]["message"]["content"].strip()
        
        duration = time.time() - start_time
        if not summary or len(summary) < 15:
            return chunk_id, None, thread_title, "LLM returned empty summary (exhausted by reasoning/CoT)", duration
            
        return chunk_id, summary, thread_title, None, duration
    except Exception as e:
        duration = time.time() - start_time
        return chunk_id, None, thread_title, str(e), duration

def main():
    parser = argparse.ArgumentParser(description="Инкрементальная техническая суммаризация чанков RAG.")
    parser.add_argument("--threads", type=int, default=4, help="Количество параллельных потоков запросов к LLM (по умолчанию: 4)")
    args = parser.parse_args()

    print("="*65)
    print("      KM Print Fix Hub - Database Chunk Summarization Utility")
    print("="*65)

    config_mgr = ConfigManager()
    index_dir = config_mgr.get("INDEX_DIR", "Index")
    db_path = os.path.join(index_dir, "knowledge_base.db")

    if not os.path.exists(db_path):
        print(f"[!] Ошибка: Файл базы данных не найден по адресу: {db_path}")
        print("Пожалуйста, убедитесь, что вы загрузили или создали индекс.")
        return

    # Получаем настройки LLM через LLMClient
    llm_client = LLMClient()
    model_name = llm_client.get_model_name()
    api_base = llm_client.get_api_base()
    provider = config_mgr.get("LLM_PROVIDER", "lmstudio")

    print(f"[*] Провайдер LLM: {provider}")
    print(f"[*] Базовый URL: {api_base}")
    print(f"[*] Используемая модель: {model_name}")
    print(f"[*] База данных: {db_path}")
    print(f"[*] Количество потоков: {args.threads}")
    if args.threads > 1:
        print("[!] ВНИМАНИЕ: Если сервер LLM запущен на слабом CPU (без GPU), большое число потоков может перегрузить систему.")

    # Подключаемся к БД
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Проверяем наличие колонки summary
    cursor.execute("PRAGMA table_info(chunks)")
    columns = [row[1] for row in cursor.fetchall()]
    if "summary" not in columns:
        print("[*] Добавление колонки 'summary' в таблицу chunks...")
        cursor.execute("ALTER TABLE chunks ADD COLUMN summary TEXT")
        conn.commit()

    # Выбираем не сжатые записи
    cursor.execute("SELECT COUNT(*) FROM chunks WHERE summary IS NULL OR summary = ''")
    to_summarize_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM chunks")
    total_count = cursor.fetchone()[0]

    already_summarized = total_count - to_summarize_count

    print(f"[*] Всего записей в базе: {total_count}")
    if already_summarized > 0:
        print(f"[+] Уже сжато в базе: {already_summarized} (будут пропущены)")
    print(f"[*] Осталось сжать: {to_summarize_count}")

    if to_summarize_count == 0:
        print("[+] Все записи в базе уже сжаты! Завершение работы.")
        conn.close()
        return

    cursor.execute("SELECT chunk_id, text, thread_title FROM chunks WHERE summary IS NULL OR summary = ''")
    rows = cursor.fetchall()

    print("\n[!] Нажмите Ctrl+C в любой момент, чтобы приостановить процесс без потери данных.\n")
    
    import time
    start_run_time = time.time()
    processed_count = 0
    success_count = 0
    failed_count = 0
    api_url = f"{api_base.rstrip('/')}/chat/completions"

    try:
        with ThreadPoolExecutor(max_workers=args.threads) as executor:
            # Запускаем задачи в пуле потоков
            future_to_row = {
                executor.submit(process_chunk, row, api_url, model_name, provider): row 
                for row in rows
            }
            
            for future in as_completed(future_to_row):
                chunk_id, summary, thread_title, error, duration = future.result()
                processed_count += 1
                
                current_done = already_summarized + processed_count
                percent = (current_done / total_count) * 100
                
                # Расчет оставшегося времени (ETA)
                elapsed_time = time.time() - start_run_time
                remaining_chunks = to_summarize_count - processed_count
                if processed_count > 0:
                    rate = processed_count / elapsed_time  # чанков в секунду
                    eta_seconds = remaining_chunks / rate
                    if eta_seconds < 60:
                        eta_str = f"{eta_seconds:.0f}с"
                    elif eta_seconds < 3600:
                        eta_str = f"{int(eta_seconds // 60)}м {int(eta_seconds % 60)}с"
                    else:
                        hours = int(eta_seconds // 3600)
                        minutes = int((eta_seconds % 3600) // 60)
                        eta_str = f"{hours}ч {minutes}м"
                else:
                    eta_str = "--"
                
                eta_prefix = f"[Осталось: {eta_str}] "
                
                if error:
                    failed_count += 1
                    print(f"[{current_done}/{total_count}] [{percent:.1f}%] {eta_prefix}[!] Ошибка ({duration:.1f}с) {chunk_id[:12]} ({thread_title[:25]}): {error}")
                else:
                    # Запись в БД происходит последовательно в главном потоке для предотвращения блокировок SQLite
                    try:
                        cursor.execute("UPDATE chunks SET summary = ? WHERE chunk_id = ?", (summary, chunk_id))
                        conn.commit()
                        success_count += 1
                        print(f"[{current_done}/{total_count}] [{percent:.1f}%] {eta_prefix}[+] Успешно ({duration:.1f}с) {chunk_id[:12]} ({thread_title[:25]})")
                    except Exception as db_err:
                        print(f"[!] Ошибка записи в БД для {chunk_id[:12]}: {db_err}")
                        
    except KeyboardInterrupt:
        print("\n[!] Процесс остановлен пользователем. Ожидание завершения запущенных потоков...")
    finally:
        conn.close()
        print(f"\n[+] Сжато фрагментов успешно: {success_count}")
        if failed_count > 0:
            print(f"[!] Ошибок обработки: {failed_count}")
        print("[+] Состояние базы данных сохранено!")

if __name__ == "__main__":
    main()
