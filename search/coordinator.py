# search/coordinator.py
# Координатор трехступенчатого поиска (FTS5 + Векторный поиск + Реранжирование) с поддержкой фильтрации и бустинга родственных моделей.

import os
import json
import re
from config.manager import ConfigManager
from search.fts_searcher import FTSSearcher
from search.searcher import Searcher
from reranker.embedding_similarity import EmbeddingSimilarityReranker

class SearchCoordinator:
    def __init__(self):
        self.config_mgr = ConfigManager()
        
        # Инициализируем поисковики и реранкер
        self.fts_searcher = FTSSearcher()
        self.vector_searcher = Searcher()
        self.reranker = EmbeddingSimilarityReranker()
        
        # Загружаем карту родственных моделей
        self.related_models = {}
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        rel_path = os.path.join(base_dir, "related_models.json")
        if os.path.exists(rel_path):
            try:
                with open(rel_path, "r", encoding="utf-8") as f:
                    self.related_models = json.load(f)
            except Exception as e:
                print(f"[!] Ошибка загрузки related_models.json: {e}")

    def _detect_model(self, doc):
        """
        Сканирует заголовок и текст чанка для автоматического определения модели KM.
        """
        models = self._detect_all_models(doc)
        if models:
            return models[0]
        return "KM-General"

    def _detect_all_models(self, doc):
        """
        Возвращает список всех моделей KM, ассоциированных с документом.
        Использует метаданные 'machine' или сканирует текст, если метаданные отсутствуют.
        """
        metadata = doc.get("metadata", {})
        machines = metadata.get("machine", [])
        if machines:
            if isinstance(machines, list):
                return [m.upper() for m in machines]
            elif isinstance(machines, str):
                return [machines.upper()]

        title = doc.get("thread_title", "")
        text = doc.get("text", "")
        combined = (title + " " + text).lower().replace('с', 'c') # Замена русской 'с' на латинскую 'c'
        
        # Загружаем пользовательский список моделей из внешнего файла
        from config import load_models_list
        user_models = load_models_list()
        
        models_to_check = []
        for m in user_models:
            m_lower = m.lower()
            models_to_check.append(m_lower)
            if not m_lower.startswith('c'):
                models_to_check.append('c' + m_lower)
                
        # Сортируем по длине строки по убыванию, чтобы избежать частичных совпадений
        models_to_check = sorted(list(set(models_to_check)), key=len, reverse=True)
        
        found = []
        for m in models_to_check:
            pattern = r'\b' + re.escape(m) + r'\b'
            if re.search(pattern, combined):
                found.append(m.upper())
                
        return found if found else ["KM-GENERAL"]

    def _translate_to_target(self, query_text, target_lang):
        try:
            import requests
            from llm.client import LLMClient
            client = LLMClient()
            api_base = client.get_api_base()
            api_url = f"{api_base.rstrip('/')}/chat/completions"
            model_name = client.get_model_name()
            
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": f"Translate the user's technical query into a brief {target_lang} technical query. Output ONLY the translated query, nothing else."},
                    {"role": "user", "content": query_text}
                ],
                "temperature": 0.0,
                "max_tokens": 15,
                "stream": False
            }
            
            provider = client.config_mgr.get("LLM_PROVIDER", "lmstudio")
            if provider == "ollama":
                payload["options"] = {
                    "num_ctx": 4096
                }
            response = requests.post(api_url, json=payload, timeout=15.0)
            if response.status_code == 200:
                translation = response.json()["choices"][0]["message"]["content"].strip()
                translation = translation.strip('"').strip("'").strip()
                if translation and len(translation) > 2:
                    print(f"[*] Target Language Translation ({target_lang}): '{query_text}' -> '{translation}'")
                    return translation
        except Exception as e:
            print(f"[!] Error translating to {target_lang}: {e}")
        return query_text

    def _translate_query_bilingual(self, query_text):
        """
        Translates query_text to both English and Russian if needed,
        returning a tuple (english_query, russian_query).
        """
        # If it's pure ASCII, assume it's English. No translation needed.
        is_english = all(ord(c) < 128 for c in query_text)
        if is_english:
            return query_text, query_text
            
        # If it has Russian characters and no other non-ASCII characters,
        # we only need to translate to English.
        has_russian = any('\u0400' <= c <= '\u04FF' for c in query_text)
        has_other_languages = any(ord(c) >= 128 and not ('\u0400' <= c <= '\u04FF') for c in query_text)
        
        if has_russian and not has_other_languages:
            en_query = self._translate_to_target(query_text, "English")
            return en_query, query_text
            
        # Otherwise (e.g. Japanese, German, etc.), translate to both English and Russian
        try:
            import requests
            from llm.client import LLMClient
            import json
            client = LLMClient()
            api_base = client.get_api_base()
            api_url = f"{api_base.rstrip('/')}/chat/completions"
            model_name = client.get_model_name()
            
            prompt = (
                "Translate the user's technical search query into BOTH English and Russian. "
                "Output strictly a JSON object with keys 'en' and 'ru'. "
                "Example: {\"en\": \"developer replacement\", \"ru\": \"замена девелопера\"}. "
                "Do not write any markdown code blocks, comments or extra text."
            )
            
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": query_text}
                ],
                "temperature": 0.0,
                "max_tokens": 60,
                "stream": False
            }
            
            provider = client.config_mgr.get("LLM_PROVIDER", "lmstudio")
            if provider == "ollama":
                payload["options"] = {
                    "num_ctx": 4096
                }
            response = requests.post(api_url, json=payload, timeout=3.0)
            if response.status_code == 200:
                res_content = response.json()["choices"][0]["message"]["content"].strip()
                if res_content.startswith("```"):
                    lines = res_content.split("\n")
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    res_content = "\n".join(lines).strip()
                
                translations = json.loads(res_content)
                en_query = translations.get("en", query_text).strip()
                ru_query = translations.get("ru", query_text).strip()
                print(f"[*] Bilingual Translation: '{query_text}' -> EN: '{en_query}' | RU: '{ru_query}'")
                return en_query, ru_query
        except Exception as e:
            print(f"[!] Error in bilingual query translation: {e}")
            
        en_fallback = self._translate_to_target(query_text, "English")
        return en_fallback, query_text

    def search(self, query_text, model="all", search_mode="all", source_filter="auto", forum_lang="all"):
        """
        Выполняет трехступенчатый поиск с фильтрацией и бустингом по моделям и источникам.
        """
        # Считываем актуальные настройки лимитов
        fts_k = self.config_mgr.get("FTS_RESULTS_COUNT", 40)
        vector_k = self.config_mgr.get("VECTOR_RESULTS_COUNT", 40)
        rerank_k = self.config_mgr.get("RERANKED_RESULTS_COUNT", 12)
        
        # 1. Определяем список разрешенных моделей для поиска
        allowed_models = None
        if model != "all" and search_mode != "all":
            if search_mode == "only":
                allowed_models = [model]
            elif search_mode == "related":
                model_key = model.upper()
                related = self.related_models.get(model_key)
                if not related and model_key.startswith('C'):
                    related = self.related_models.get(model_key[1:])
                if not related:
                    related = []
                
                # Расширяем список разрешенных моделей с префиксом 'C' и без него
                raw_list = [model] + related
                expanded = []
                for m in raw_list:
                    m_clean = m.strip()
                    expanded.append(m_clean)
                    if m_clean.upper().startswith('C'):
                        expanded.append(m_clean[1:])
                    else:
                        expanded.append('C' + m_clean)
                allowed_models = list(set(expanded))

        # Получаем английский и русский варианты запроса для поиска по разноязычным базам
        if forum_lang == "ru":
            has_russian = any('\u0400' <= c <= '\u04FF' for c in query_text)
            if not has_russian:
                ru_query = self._translate_to_target(query_text, "Russian")
            else:
                ru_query = query_text
            en_query = ru_query
        elif forum_lang == "en":
            is_english = all(ord(c) < 128 for c in query_text)
            if not is_english:
                en_query = self._translate_to_target(query_text, "English")
            else:
                en_query = query_text
            ru_query = en_query
        else: # forum_lang == "all"
            is_english = all(ord(c) < 128 for c in query_text)
            has_russian = any('\u0400' <= c <= '\u04FF' for c in query_text)
            has_other_languages = any(ord(c) >= 128 and not ('\u0400' <= c <= '\u04FF') for c in query_text)
            
            if is_english:
                en_query = query_text
                ru_query = self._translate_to_target(query_text, "Russian")
            elif has_russian and not has_other_languages:
                ru_query = query_text
                en_query = self._translate_to_target(query_text, "English")
            else:
                en_query, ru_query = self._translate_query_bilingual(query_text)

        # 2. Полнотекстовый поиск (FTS5) с фильтрацией на уровне SQL
        if source_filter == "official":
            fts_results = self.fts_searcher.search(en_query, k=fts_k, allowed_models=allowed_models, source_filter=source_filter)
        elif source_filter in ["forum", "auto"]:
            if en_query != ru_query:
                results_ru = self.fts_searcher.search(ru_query, k=fts_k, allowed_models=allowed_models, source_filter=source_filter)
                results_en = self.fts_searcher.search(en_query, k=fts_k, allowed_models=allowed_models, source_filter=source_filter)
                seen_ids = set()
                fts_results = []
                for doc, score in results_ru + results_en:
                    if doc["id"] not in seen_ids:
                        seen_ids.add(doc["id"])
                        fts_results.append((doc, score))
            else:
                target_q = ru_query if forum_lang == "ru" else en_query
                fts_results = self.fts_searcher.search(target_q, k=fts_k, allowed_models=allowed_models, source_filter=source_filter)
        else:
            fts_results = self.fts_searcher.search(query_text, k=fts_k, allowed_models=allowed_models, source_filter=source_filter)
            
        # Фильтруем FTS5 результаты по языку форума
        filtered_fts = []
        for doc, score in fts_results:
            doc_source = doc.get("metadata", {}).get("source", "tradeprint")
            if doc_source != "official":
                if forum_lang == "ru" and doc_source != "tradeprint":
                    continue
                if forum_lang == "en" and doc_source == "tradeprint":
                    continue
            filtered_fts.append((doc, score))
        fts_results = filtered_fts
        
        # 3. Векторный поиск
        is_mock = self.vector_searcher.embeddings.is_mock()
        
        if is_mock:
            # В режиме MockEmbeddings векторный поиск не имеет смысла, опираемся на FTS5
            vector_results = []
        else:
            # Получаем кандидатов векторного поиска
            if source_filter == "official" and en_query != query_text:
                vector_candidates = self.vector_searcher.search(en_query, k=vector_k * 5)
            elif source_filter in ["forum", "auto"]:
                if en_query != ru_query:
                    candidates_ru = self.vector_searcher.search(ru_query, k=vector_k)
                    candidates_en = self.vector_searcher.search(en_query, k=vector_k)
                    seen_ids = set()
                    vector_candidates = []
                    for doc, score in candidates_ru + candidates_en:
                        if doc["id"] not in seen_ids:
                            seen_ids.add(doc["id"])
                            vector_candidates.append((doc, score))
                else:
                    target_q = ru_query if forum_lang == "ru" else en_query
                    vector_candidates = self.vector_searcher.search(target_q, k=vector_k * 2)
            else:
                needs_filtering = bool(allowed_models or (source_filter and source_filter != "auto"))
                k_to_search = max(200, vector_k * 5) if needs_filtering else vector_k
                vector_candidates = self.vector_searcher.search(query_text, k=k_to_search)
            
            filtered_vector = []
            for doc, score in vector_candidates:
                # Определяем все подходящие модели
                doc_models = self._detect_all_models(doc)
                doc["model"] = doc_models[0] if doc_models else "KM-General"
                
                # Фильтруем по источнику
                doc_source = doc.get("metadata", {}).get("source", "tradeprint")
                if source_filter == "official" and doc_source != "official":
                    continue
                if source_filter == "forum" and doc_source == "official":
                    continue
                    
                # Фильтруем по языку форума
                if doc_source != "official":
                    if forum_lang == "ru" and doc_source != "tradeprint":
                        continue
                    if forum_lang == "en" and doc_source == "tradeprint":
                        continue
                
                # Фильтруем по моделям, если задано
                if allowed_models:
                    if doc_models != ["KM-GENERAL"]:
                        match = any(m.lower() in [dm.lower() for dm in doc_models] for m in allowed_models)
                    else:
                        combined = (doc["thread_title"] + " " + doc["text"]).lower().replace('с', 'c')
                        match = any(m.lower() in combined for m in allowed_models)
                    if not match:
                        continue
                
                filtered_vector.append((doc, score))
                if len(filtered_vector) >= vector_k:
                    break
            vector_results = filtered_vector

        # 4. Объединение результатов и отслеживание источников
        unique_docs = {}
        fts_log = []
        vector_log = []
        
        for doc, score in fts_results:
            doc_id = doc["id"]
            doc_model = self._detect_model(doc)
            doc["model"] = doc_model
            unique_docs[doc_id] = doc
            fts_log.append({
                "id": doc_id,
                "title": doc["thread_title"],
                "model": doc_model,
                "score": round(score, 4)
            })
            
        for doc, score in vector_results:
            doc_id = doc["id"]
            doc_model = doc.get("model") or self._detect_model(doc)
            doc["model"] = doc_model
            unique_docs[doc_id] = doc
            vector_log.append({
                "id": doc_id,
                "title": doc["thread_title"],
                "model": doc_model,
                "score": round(score, 4)
            })
            
        candidate_docs = list(unique_docs.values())
        
        # 5. Реранжирование кандидатов
        if is_mock:
            # В режиме MockEmbeddings пропускаем реранжирование на основе векторов,
            # чтобы сохранить исходный правильный порядок лексического поиска FTS5.
            reranked = [(doc, score) for doc, score in fts_results]
        else:
            # Разделяем кандидатов по языку источника для точного реранжирования
            ru_candidates = []
            en_candidates = []
            for doc in candidate_docs:
                doc_source = doc.get("metadata", {}).get("source", "tradeprint")
                if doc_source == "tradeprint":
                    ru_candidates.append(doc)
                else:
                    en_candidates.append(doc)
            
            reranked_ru = self.reranker.rerank(ru_query, ru_candidates, k=len(ru_candidates)) if ru_candidates else []
            reranked_en = self.reranker.rerank(en_query, en_candidates, k=len(en_candidates)) if en_candidates else []
            
            # Объединяем и сортируем заново по скору схожести
            reranked = reranked_ru + reranked_en
            reranked.sort(key=lambda x: x[1], reverse=True)
        
        # 6. Бустинг и скоринг оценок на основе совпадения с моделью (Section 4, task_05.md)
        # score = model_score + 0.6 * semantic_val
        boosted_results = []
        
        # Получаем максимальный скор для нормализации лексических оценок (FTS5)
        max_score = max([s for d, s in reranked]) if reranked else 1.0
        if max_score <= 0:
            max_score = 1.0
            
        # Индексируем лексические оценки по FTS5 для гибридного поиска
        fts_scores = {doc["id"]: s for doc, s in fts_results}
        max_fts_score = max(fts_scores.values()) if fts_scores else 1.0
        if max_fts_score <= 0:
            max_fts_score = 1.0
            
        for doc, score in reranked:
            doc_id = doc["id"]
            
            # Семантическое сходство приводим к [0, 1]
            if is_mock:
                semantic_val = score / max_score
            else:
                # Гибридный поиск: объединяем FTS5 (лексический) и векторный (семантический) скоры
                fts_val = fts_scores.get(doc_id, 0.0) / max_fts_score
                vector_val = score
                semantic_val = 0.4 * fts_val + 0.6 * vector_val
            
            model_score = 0.0
            if model != "all":
                doc_models = self._detect_all_models(doc)
                
                # Check strict match
                if any(m.lower() == model.lower() for m in doc_models):
                    model_score = 1.0
                    doc["model"] = model.upper()
                # Check related match
                elif allowed_models and any(m.lower() in [dm.lower() for dm in doc_models] for m in allowed_models):
                    model_score = 0.7
                    matched_related = [m for m in allowed_models if m.lower() in [dm.lower() for dm in doc_models]]
                    if matched_related:
                        doc["model"] = matched_related[0].upper()
                # Check general
                elif "KM-GENERAL" in doc_models:
                    model_score = 0.0
                    doc["model"] = "KM-General"
                else:
                    model_score = -1.0  # Неродственная модель (шум)
            else:
                model_score = 0.0
                doc_models = self._detect_all_models(doc)
                doc["model"] = doc_models[0] if doc_models else "KM-General"
                
            # Приоритет официальной документации (Official Bonus)
            doc_source = doc.get("metadata", {}).get("source", "tradeprint")
            official_bonus = 0.08 if doc_source == "official" else 0.0
            
            final_score = model_score + 0.6 * semantic_val + official_bonus
            boosted_results.append((doc, final_score))
            
        # Повторно сортируем по взвешенному скору
        boosted_results.sort(key=lambda x: x[1], reverse=True)
        reranked = boosted_results[:rerank_k]

        # Оптимизация контекста (Context Optimizer)
        opt_info = None
        if self.config_mgr.get("ENABLE_CONTEXT_OPTIMIZER", False):
            try:
                from search.context_optimizer import LLMContextOptimizer
                optimizer = LLMContextOptimizer()
                words_before = sum(len(d.get("text", "").split()) for d, _ in reranked)
                num_docs_before = len(reranked)
                
                reranked = optimizer.optimize(reranked)
                
                words_after = sum(len(d.get("text", "").split()) for d, _ in reranked)
                num_docs_after = len(reranked)
                
                opt_info = {
                    "docs_before": num_docs_before,
                    "docs_after": num_docs_after,
                    "words_before": words_before,
                    "words_after": words_after,
                    "saved_pct": round((1.0 - (words_after / words_before)) * 100, 1) if words_before > 0 else 0.0
                }
            except Exception as e:
                print(f"[!] Error in LLMContextOptimizer: {e}")

        # Формируем лог для диагностики (Debug)
        reranked_log = []
        for doc, score in reranked:
            reranked_log.append({
                "id": doc["id"],
                "title": doc["thread_title"],
                "model": doc.get("model", "KM-General"),
                "score": round(score, 4)
            })
            
        debug_info = {
            "query": query_text,
            "selected_model": model,
            "search_mode": search_mode,
            "fts_found": fts_log,
            "vector_found": vector_log,
            "reranked": reranked_log,
            "context_optimization": opt_info
        }
        
        # Enrich reranked documents with their summary fields from SQLite
        if reranked:
            import sqlite3
            try:
                conn = sqlite3.connect(self.fts_searcher.db_path)
                cursor = conn.cursor()
                for doc, _ in reranked:
                    doc_id = doc["id"]
                    cursor.execute("SELECT summary FROM chunks WHERE chunk_id = ?", (doc_id,))
                    row = cursor.fetchone()
                    if row:
                        doc["summary"] = row[0]
                conn.close()
            except Exception as e:
                print(f"[!] Error fetching summaries during search: {e}")

        return reranked, debug_info
