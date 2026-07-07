# search/fts_searcher.py
# Модуль полнотекстового поиска по базе знаний с помощью SQLite FTS5.

import os
import re
import json
import sqlite3
from config.manager import ConfigManager

class FTSSearcher:
    def __init__(self, db_path=None):
        config_mgr = ConfigManager()
        if db_path is None:
            index_dir = config_mgr.get("INDEX_DIR", "Index")
            self.db_path = os.path.join(index_dir, "knowledge_base.db")
        else:
            self.db_path = db_path
            
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"База данных SQLite не найдена по пути: {self.db_path}")

    def _prepare_query(self, raw_query):
        """
        Очищает запрос и подготавливает его для синтаксиса FTS5 MATCH.
        Слова преобразуются в префиксные совпадения и объединяются через OR.
        Пример: 'Ricoh SC899' -> 'Ricoh* OR SC899*'
        """
        # Находим все слова (буквенно-цифровые символы и дефисы)
        words = re.findall(r'\b[a-zA-Z0-9а-яА-ЯёЁ\-]+\b', raw_query)
        if not words:
            return ""
            
        # Формируем термы с префиксным поиском
        terms = [f'"{w}"*' for w in words]
        return " OR ".join(terms)

    def search(self, query_text, k=25, allowed_models=None, source_filter=None):
        """
        Выполняет полнотекстовый поиск.
        Возвращает список кортежей: (document_dict, fts_score)
        """
        cleaned_query = self._prepare_query(query_text)
        if not cleaned_query:
            return []
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # SQLite FTS5 rank: меньшие значения (наиболее отрицательные) означают лучшую релевантность.
        # Мы возвращаем score как -rank, чтобы более высокая релевантность имела больший скор.
        sql = """
        SELECT f.chunk_id, -f.rank, c.thread_id, c.thread_title, c.url, c.chunk_index, c.text, c.metadata_json
        FROM fts_chunks f
        JOIN chunks c ON f.chunk_id = c.chunk_id
        WHERE fts_chunks MATCH ?
        """
        
        params = [cleaned_query]
        
        if allowed_models:
            model_conditions = []
            for m in allowed_models:
                model_conditions.append("(c.thread_title LIKE ? OR c.text LIKE ?)")
                params.append(f"%{m}%")
                params.append(f"%{m}%")
            if model_conditions:
                sql += " AND (" + " OR ".join(model_conditions) + ")"
                
        # Фильтрация по источнику (Official / Forum)
        if source_filter == "official":
            sql += " AND c.source = 'official'"
        elif source_filter == "forum":
            sql += " AND c.source != 'official'"
                
        sql += """
        ORDER BY f.rank ASC
        LIMIT ?
        """
        params.append(k)
        
        results = []
        try:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            
            for row in rows:
                chunk_id, score, thread_id, thread_title, url, chunk_index, text, metadata_json = row
                try:
                    metadata = json.loads(metadata_json)
                except Exception:
                    metadata = {}
                    
                doc = {
                    "id": chunk_id,
                    "thread_id": thread_id,
                    "thread_title": thread_title,
                    "url": url,
                    "chunk_index": chunk_index,
                    "text": text,
                    "metadata": metadata
                }
                results.append((doc, float(score)))
        except sqlite3.OperationalError as e:
            print(f"[!] Ошибка SQLite FTS5 при запросе '{cleaned_query}': {e}")
        finally:
            conn.close()
            
        return results

    def get_chunk(self, chunk_id):
        """
        Возвращает детальную информацию о конкретном чанке по его ID.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        sql = "SELECT chunk_id, thread_id, thread_title, url, chunk_index, text, metadata_json FROM chunks WHERE chunk_id = ?"
        try:
            cursor.execute(sql, (chunk_id,))
            row = cursor.fetchone()
            if row:
                try:
                    metadata = json.loads(row["metadata_json"])
                except Exception:
                    metadata = {}
                return {
                    "id": row["chunk_id"],
                    "thread_id": row["thread_id"],
                    "thread_title": row["thread_title"],
                    "url": row["url"],
                    "chunk_index": row["chunk_index"],
                    "text": row["text"],
                    "metadata": metadata
                }
        except Exception as e:
            print(f"[!] Ошибка получения чанка {chunk_id}: {e}")
        finally:
            conn.close()
        return None
