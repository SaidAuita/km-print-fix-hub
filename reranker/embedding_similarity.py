# reranker/embedding_similarity.py
# Реранкер на основе косинусного сходства эмбеддингов кандидатов и запроса.

import os
import sqlite3
import numpy as np
from reranker.base import BaseReranker
from config.manager import ConfigManager
from embeddings.factory import get_embeddings_provider

class EmbeddingSimilarityReranker(BaseReranker):
    def __init__(self, db_path=None):
        config_mgr = ConfigManager()
        if db_path is None:
            index_dir = config_mgr.get("INDEX_DIR", "Index")
            self.db_path = os.path.join(index_dir, "knowledge_base.db")
        else:
            self.db_path = db_path
            
        # Получаем текущего провайдера эмбеддингов
        self.embeddings_provider = get_embeddings_provider()

    def _load_embeddings(self, chunk_ids):
        """
        Загружает векторы эмбеддингов для списка chunk_ids из базы SQLite за один запрос.
        """
        if not chunk_ids or not os.path.exists(self.db_path):
            return {}
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Формируем плейсхолдеры для IN-запроса
        placeholders = ",".join(["?"] * len(chunk_ids))
        sql = f"SELECT chunk_id, embedding FROM chunks WHERE chunk_id IN ({placeholders})"
        
        id_to_vector = {}
        try:
            cursor.execute(sql, chunk_ids)
            rows = cursor.fetchall()
            for chunk_id, emb_bytes in rows:
                if emb_bytes:
                    vector = np.frombuffer(emb_bytes, dtype=np.float32)
                    id_to_vector[chunk_id] = vector
        except Exception as e:
            print(f"[!] Ошибка загрузки векторов из SQLite для реранжирования: {e}")
        finally:
            conn.close()
            
        return id_to_vector

    def rerank(self, query_text, candidate_docs, k=10):
        if not candidate_docs:
            return []
            
        # 1. Вычисляем эмбеддинг поискового запроса
        try:
            query_vector = self.embeddings_provider.embed_query(query_text)
            q_vec = np.array(query_vector, dtype=np.float32)
            q_norm = np.linalg.norm(q_vec)
        except Exception as e:
            print(f"[!] Ошибка вычисления эмбеддинга запроса при реранжировании: {e}")
            # В случае ошибки возвращаем кандидатов как есть
            return [(doc, 0.5) for doc in candidate_docs[:k]]
            
        if q_norm == 0:
            return [(doc, 0.0) for doc in candidate_docs[:k]]
            
        # 2. Выбираем chunk_ids кандидатов и загружаем их сохраненные векторы
        chunk_ids = [doc["id"] for doc in candidate_docs]
        id_to_vector = self._load_embeddings(chunk_ids)
        
        # 3. Вычисляем сходство
        scored_candidates = []
        for doc in candidate_docs:
            doc_id = doc["id"]
            doc_vector = id_to_vector.get(doc_id)
            
            if doc_vector is not None:
                doc_norm = np.linalg.norm(doc_vector)
                if doc_norm > 0:
                    similarity = float(np.dot(doc_vector, q_vec) / (doc_norm * q_norm))
                else:
                    similarity = 0.0
            else:
                similarity = 0.0
                
            scored_candidates.append((doc, similarity))
            
        # 4. Сортируем по убыванию сходства и отдаем топ-k
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        return scored_candidates[:k]
