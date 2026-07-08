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
        title = doc.get("thread_title", "")
        text = doc.get("text", "")
        combined = (title + " " + text).lower().replace('с', 'c') # Замена русской 'с' на латинскую 'c'
        
        # Список моделей от специфических к общим (от современных линеек к более старым)
        models_to_check = [
            # AccurioPress / Press Color High-End
            "c14010s", "c14010", "14010s", "14010",
            "c12010s", "c12010", "12010s", "12010",
            "c10500s", "c10500", "10500s", "10500",
            "c14000", "c12000", "14000", "12000",
            "c6100", "c6085", "6100", "6085",
            # AccurioPress C4080 / C4070 / C4065
            "c4080", "c4070", "c4065", "4080", "4070", "4065",
            # AccurioPress 3080 / 3070
            "c3080", "c3070", "3080", "3070",
            # bizhub PRESS 2070 / 2060
            "c2070", "c2060", "2070", "2060",
            # bizhub PRESS 1070 / 1060 / 1060L
            "c1070l", "c1060l", "c1070", "c1060", "1070l", "1060l", "1070", "1060",
            # bizhub PRESS 8000 / 7000 / 6000
            "c8000", "c7000", "c6000", "8000", "7000", "6000",
            # bizhub PRO 6501 / 5501 / 6500 / 5500
            "6501", "5501", "6500", "5500",
            # Office Color C250i / C300i / C360i / C450i / C550i / C650i / C750i (i-series)
            "c750i", "c650i", "c550i", "c450i", "c360i", "c300i", "c250i",
            # Office Color C258 / C308 / C368 / C458 / C558 / C658 (8-series)
            "c658", "c558", "c458", "c368", "c308", "c258",
            # Office Color C224 / C284 / C364 / C454 / C554 (with & without e)
            "c554e", "c454e", "c364e", "c284e", "c224e",
            "c554", "c454", "c364", "c284", "c224",
            # Office Color C220 / C280 / C360 (0-series)
            "c360", "c280", "c220",
            # Office Color Early C250 / C252 / C253 / C353 / C451 / C452
            "c452", "c451", "c353", "c253", "c252", "c250",
            # B&W Production (AccurioPress B&W & Pro)
            "6136", "6120", "1250", "1200", "1100", "1052", "1051", "1050", "950", "920"
        ]
        
        for m in models_to_check:
            pattern = r'\b' + re.escape(m) + r'\b'
            if re.search(pattern, combined):
                return m.upper()
            if not m.startswith('c'):
                pattern_c = r'\bc' + re.escape(m) + r'\b'
                if re.search(pattern_c, combined):
                    return m.upper()
                    
        return "KM-General"

    def _translate_to_target(self, query_text, target_lang):
        try:
            import requests
            from llm.client import LLMClient
            client = LLMClient()
            api_base = client.config_mgr.get("LM_STUDIO_API_BASE", "http://localhost:1234/v1")
            api_url = f"{api_base.rstrip('/')}/chat/completions"
            model_name = client._get_loaded_model_name()
            
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
            response = requests.post(api_url, json=payload, timeout=2.0)
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
        has_russian = any(c in 'аяАЯёЁ' for c in query_text)
        has_other_languages = any(ord(c) >= 128 and c not in 'аяАЯёЁ' and not c.lower() in 'abcdefghijklmnopqrstuvwxyz' for c in query_text)
        
        if has_russian and not has_other_languages:
            en_query = self._translate_to_target(query_text, "English")
            return en_query, query_text
            
        # Otherwise (e.g. Japanese, German, etc.), translate to both English and Russian
        try:
            import requests
            from llm.client import LLMClient
            import json
            client = LLMClient()
            api_base = client.config_mgr.get("LM_STUDIO_API_BASE", "http://localhost:1234/v1")
            api_url = f"{api_base.rstrip('/')}/chat/completions"
            model_name = client._get_loaded_model_name()
            
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

    def search(self, query_text, model="all", search_mode="all", source_filter="auto"):
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
                allowed_models = [model] + self.related_models.get(model, [])

        # Получаем английский и русский варианты запроса для поиска по разноязычным базам
        en_query = query_text
        ru_query = query_text
        is_english = all(ord(c) < 128 for c in query_text)
        if not is_english:
            en_query, ru_query = self._translate_query_bilingual(query_text)

        # 2. Полнотекстовый поиск (FTS5) с фильтрацией на уровне SQL
        if source_filter == "official":
            fts_results = self.fts_searcher.search(en_query, k=fts_k, allowed_models=allowed_models, source_filter=source_filter)
        elif source_filter in ["forum", "auto"] and (en_query != query_text or ru_query != query_text):
            results_ru = self.fts_searcher.search(ru_query, k=fts_k, allowed_models=allowed_models, source_filter=source_filter)
            results_en = self.fts_searcher.search(en_query, k=fts_k, allowed_models=allowed_models, source_filter=source_filter)
            seen_ids = set()
            fts_results = []
            for doc, score in results_ru + results_en:
                if doc["id"] not in seen_ids:
                    seen_ids.add(doc["id"])
                    fts_results.append((doc, score))
        else:
            fts_results = self.fts_searcher.search(query_text, k=fts_k, allowed_models=allowed_models, source_filter=source_filter)
        
        # 3. Векторный поиск
        is_mock = self.vector_searcher.embeddings.is_mock()
        
        if is_mock:
            # В режиме MockEmbeddings векторный поиск не имеет смысла, опираемся на FTS5
            vector_results = []
        else:
            # Получаем кандидатов векторного поиска
            if source_filter == "official" and en_query != query_text:
                vector_candidates = self.vector_searcher.search(en_query, k=vector_k * 5)
            elif source_filter in ["forum", "auto"] and (en_query != query_text or ru_query != query_text):
                candidates_ru = self.vector_searcher.search(ru_query, k=vector_k)
                candidates_en = self.vector_searcher.search(en_query, k=vector_k)
                seen_ids = set()
                vector_candidates = []
                for doc, score in candidates_ru + candidates_en:
                    if doc["id"] not in seen_ids:
                        seen_ids.add(doc["id"])
                        vector_candidates.append((doc, score))
            else:
                needs_filtering = bool(allowed_models or (source_filter and source_filter != "auto"))
                k_to_search = max(200, vector_k * 5) if needs_filtering else vector_k
                vector_candidates = self.vector_searcher.search(query_text, k=k_to_search)
            
            filtered_vector = []
            for doc, score in vector_candidates:
                # Определяем модель
                doc_model = self._detect_model(doc)
                doc["model"] = doc_model
                
                # Фильтруем по источнику
                doc_source = doc.get("metadata", {}).get("source", "tradeprint")
                if source_filter == "official" and doc_source != "official":
                    continue
                if source_filter == "forum" and doc_source == "official":
                    continue
                
                # Фильтруем по моделям, если задано
                if allowed_models:
                    if doc_model != "KM-General":
                        match = any(m.lower() == doc_model.lower() for m in allowed_models)
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
            reranked = self.reranker.rerank(query_text, candidate_docs, k=len(candidate_docs))
        
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
            doc_model = doc.get("model", "KM-General")
            
            # Семантическое сходство приводим к [0, 1]
            if is_mock:
                semantic_val = score / max_score
            else:
                # Гибридный поиск: объединяем FTS5 (лексический) и векторный (семантический) скоры
                fts_val = fts_scores.get(doc_id, 0.0) / max_fts_score
                vector_val = score
                semantic_val = 0.4 * fts_val + 0.6 * vector_val
            
            if model != "all":
                if doc_model.lower() == model.lower():
                    model_score = 1.0
                elif allowed_models and any(m.lower() == doc_model.lower() for m in allowed_models):
                    model_score = 0.7
                elif doc_model == "KM-General":
                    model_score = 0.0
                else:
                    model_score = -1.0  # Неродственная модель (шум)
            else:
                model_score = 0.0
                
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
        
        return reranked, debug_info
