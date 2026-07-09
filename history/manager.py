# history/manager.py
# Менеджер истории диалогов на SQLite.

import os
import sqlite3
import json
from datetime import datetime

class HistoryManager:
    def __init__(self, db_path="history.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            query TEXT,
            answer TEXT,
            sources_json TEXT
        )
        """)
        conn.commit()
        conn.close()

    def add_chat(self, query, answer, sources):
        """
        Сохраняет новый диалог в историю.
        sources: список документов, переданный в формате [{'id': ..., 'title': ..., 'url': ...}]
        """
        timestamp = datetime.now().isoformat()
        sources_json = json.dumps(sources, ensure_ascii=False)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_history (timestamp, query, answer, sources_json) VALUES (?, ?, ?, ?)",
            (timestamp, query, answer, sources_json)
        )
        chat_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return chat_id

    def get_history(self):
        """
        Возвращает всю историю, начиная с самых свежих записей.
        """
        conn = sqlite3.connect(self.db_path)
        # Позволяет обращаться к колонкам по именам, а не только по индексам
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, timestamp, query, answer, sources_json FROM chat_history ORDER BY id DESC")
        rows = cursor.fetchall()
        
        history = []
        for row in rows:
            try:
                sources = json.loads(row["sources_json"])
            except Exception:
                sources = []
                
            history.append({
                "id": row["id"],
                "timestamp": row["timestamp"],
                "query": row["query"],
                "answer": row["answer"],
                "sources": sources
            })
            
        conn.close()
        return history

    def delete_chat(self, chat_id):
        """
        Удаляет отдельный диалог по его ID.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history WHERE id = ?", (chat_id,))
        conn.commit()
        conn.close()

    def clear_history(self):
        """
        Очищает всю историю диалогов.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM chat_history")
        conn.commit()
        conn.close()
