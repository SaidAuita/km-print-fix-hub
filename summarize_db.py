# summarize_db.py
# Скрипт для инкрементального технического сжатия чанков в базе данных.

import os
import sys
import sqlite3
import json
import requests

# Добавляем корень проекта в пути импорта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config.manager import ConfigManager
from llm.client import LLMClient

def main():
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

    print(f"[*] Всего записей в базе: {total_count}")
    print(f"[*] Записей для сжатия: {to_summarize_count}")

    if to_summarize_count == 0:
        print("[+] Все записи в базе уже сжаты! Завершение работы.")
        conn.close()
        return

    cursor.execute("SELECT chunk_id, text, thread_title FROM chunks WHERE summary IS NULL OR summary = ''")
    rows = cursor.fetchall()

    print("\n[!] Нажмите Ctrl+C в любой момент, чтобы приостановить процесс без потери данных.\n")
    processed_count = 0

    api_url = f"{api_base.rstrip('/')}/chat/completions"

    try:
        for chunk_id, text, thread_title in rows:
            print(f"[{processed_count + 1}/{to_summarize_count}] Сжатие фрагмента {chunk_id[:12]}... ({thread_title[:35]})")
            
            # Строим промпт для сжатия
            prompt = (
                "Сделай краткую техническую выжимку из этого обсуждения или документа о Konica Minolta на русском языке.\n"
                "Выдели только суть в строго следующем формате:\n"
                "Проблема: <коротко суть проблемы>\n"
                "Причина: <возможные причины, если упомянуты, иначе оставить пустым>\n"
                "Решение: <способы решения, если указаны, иначе оставить пустым>\n"
                "Модели: <конкретные модели принтеров, если упомянуты, иначе оставить пустым>\n\n"
                f"Текст для сжатия:\n{text}"
            )

            payload = {
                "model": model_name,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.1,
                "max_tokens": 500,
                "stream": False
            }

            if provider == "ollama":
                payload["options"] = {
                    "num_ctx": 4096  # Для сжатия одного чанка 4096 токенов более чем достаточно
                }

            try:
                # Отправляем запрос
                response = requests.post(api_url, json=payload, timeout=60.0)
                response.raise_for_status()
                data = response.json()
                summary = data["choices"][0]["message"]["content"].strip()
                
                # Обновляем базу данных
                cursor.execute("UPDATE chunks SET summary = ? WHERE chunk_id = ?", (summary, chunk_id))
                conn.commit()
                processed_count += 1
                
            except Exception as e:
                print(f"[!] Ошибка запроса к LLM для {chunk_id}: {e}")
                print("[*] Переход к следующему фрагменту...")

    except KeyboardInterrupt:
        print("\n[!] Процесс остановлен пользователем.")
    finally:
        conn.close()
        print(f"\n[+] Сжато фрагментов: {processed_count}")
        print("[+] Состояние базы данных сохранено!")

if __name__ == "__main__":
    main()
