# llm/client.py
# Клиент для отправки RAG-запросов к API LM Studio.

import json
import requests
from config.manager import ConfigManager

class LLMClient:
    def __init__(self):
        self.config_mgr = ConfigManager()

    def _get_loaded_model_name(self):
        """
        Запрашивает список активных моделей из LM Studio.
        """
        api_base = self.config_mgr.get("LM_STUDIO_API_BASE", "http://localhost:1234/v1")
        models_url = f"{api_base.rstrip('/')}/models"
        try:
            response = requests.get(models_url, timeout=3)
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                if models:
                    return models[0].get("id")
        except Exception:
            pass
        return "google/gemma-4-12b-qat"

    def build_prompt(self, query, documents, strict_mode=False, show_reasoning=False):
        """
        Формирует контекст с ограничением размера по словам и строит промпт.
        """
        max_words = self.config_mgr.get("MAX_CONTEXT_SIZE_WORDS", 3000)
        
        context_parts = []
        current_words = 0
        used_documents = []
        
        for idx, (doc, score) in enumerate(documents, 1):
            text = doc.get("text", "")
            chunk_words = len(text.split())
            
            # Проверяем лимит контекста
            if current_words + chunk_words > max_words and context_parts:
                break
                
            current_words += chunk_words
            used_documents.append((doc, score))
            
            doc_model = doc.get("model", "KM-General")
            doc_source = doc.get("metadata", {}).get("source", "tradeprint")
            
            if doc_source == "official":
                chunk_content = (
                    f"SOURCE {idx} [Official]\n"
                    f"Document: {doc.get('metadata', {}).get('document', 'Unknown Document')}\n"
                    f"Page: {doc.get('metadata', {}).get('page', 'Unknown Page')}\n"
                    f"Text: {text}\n"
                )
            else:
                forum_name = "forum.trade-print.ru"
                if doc_source == "copytechnet":
                    forum_name = "copytechnet.com"
                elif doc_source == "printplanet":
                    forum_name = "printplanet.com"
                elif doc_source == "colorprinting":
                    forum_name = "colorprintingforum.com"
                
                authors_str = ", ".join(doc.get("metadata", {}).get("authors", [])) or doc.get("author", "unknown")
                thread_title = doc.get("thread_title", "Unknown Thread")
                
                chunk_content = (
                    f"SOURCE {idx} [Forum]\n"
                    f"Forum: {forum_name}\n"
                    f"Thread: {thread_title}\n"
                    f"Author: {authors_str}\n"
                    f"Text: {text}\n"
                )
            context_parts.append(chunk_content)
            
        context_text = "\n\n".join(context_parts)
        
        system_prompt = self.config_mgr.get("SYSTEM_PROMPT", (
            "Ты — инженер технической поддержки Konica Minolta.\n"
            "Отвечай ТОЛЬКО на русском языке.\n"
            "Используй ТОЛЬКО предоставленный контекст.\n"
            "Запрещено:\n"
            "* объединять разные модели в один диагноз\n"
            "* добавлять новые причины вне контекста\n"
            "* делать обобщения между моделями без явной пометки\n\n"
            "Если информация относится к другой модели — обязательно укажи это.\n\n"
            "ФОРМАТ ОТВЕТА:\n\n"
            "Вывод:\n"
            "...\n\n"
            "Причины:\n"
            "...\n\n"
            "Что проверить:\n"
            "...\n\n"
            "Источники:\n"
            "* Model X"
        ))
        
        # Инструкция для LLM по приоритету официальной документации (Section 7, task_08.md)
        system_prompt += (
            "\n\nПРАВИЛА ИСТОЧНИКОВ:\n"
            "* Официальная документация (Official) является основным источником истины.\n"
            "* Сообщения с форумов (Forum) используются как практический опыт инженеров.\n"
            "* Если информация противоречит друг другу, приоритет имеет Official.\n"
            "* Если форум предлагает решение, отсутствующее в официальной документации, необходимо явно указать, что это практический опыт пользователей, а не официальная рекомендация.\n"
            "* При ответе ОБЯЗАТЕЛЬНО ссылайся на источник каждого утверждения исключительно в формате [SOURCE X] (например, [SOURCE 1], [SOURCE 2]), где X — номер источника из контекста.\n"
            "* ВНИМАНИЕ: Номера постов в тексте (например, Пост #32) НЕ являются номерами источников! Ссылайтесь исключительно на номера X из заголовков 'SOURCE X' (от 1 до общего числа предоставленных источников)."
        )
        
        if strict_mode:
            system_prompt += (
                "\n\n[ВНИМАНИЕ: СТРОГИЙ РЕЖИМ. Категорически запрещено переносить выводы с одной модели на другую. "
                "Если в предоставленном контексте нет информации конкретно по запрашиваемой модели, "
                "честно ответьте, что по данной модели на форуме обсуждений не найдено.]"
            )
            
        if not show_reasoning:
            system_prompt += (
                "\n\n* ЗАПРЕЩЕНО выводить любые предварительные рассуждения, размышления вслух, "
                "пошаговый анализ или блок мыслей (Chain of Thought / <thought>). "
                "Пиши СРАЗУ итоговый ответ в указанном формате."
            )
        
        user_prompt = (
            f"### SYSTEM\n\n"
            f"{system_prompt}\n\n"
            f"---\n\n"
            f"### ВОПРОС\n\n"
            f"{query}\n\n"
            f"---\n\n"
            f"### КОНТЕКСТ\n\n"
            f"{context_text}"
        )
        
        return system_prompt, user_prompt, used_documents

    def generate_answer_stream(self, system_prompt, user_prompt):
        """
        Генерирует ответ в виде потока чанков (SSE).
        """
        api_base = self.config_mgr.get("LM_STUDIO_API_BASE", "http://localhost:1234/v1")
        api_url = f"{api_base.rstrip('/')}/chat/completions"
        model_name = self._get_loaded_model_name()
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": self.config_mgr.get("LLM_TEMPERATURE", 0.3),
            "max_tokens": self.config_mgr.get("LLM_MAX_TOKENS", 1024),
            "stream": True
        }
        
        try:
            response = requests.post(api_url, json=payload, stream=True, timeout=300)
            response.raise_for_status()
            
            for line in response.iter_lines():
                if not line:
                    continue
                line_str = line.decode("utf-8").strip()
                if line_str.startswith("data: "):
                    data_json = line_str[6:]
                    if data_json == "[DONE]":
                        break
                    try:
                        data = json.loads(data_json)
                        if "error" in data:
                            error_msg = data["error"].get("message", str(data["error"]))
                            raise Exception(f"Ошибка от LM Studio: {error_msg}")
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "") or delta.get("reasoning_content", "")
                        if content:
                            yield content
                    except Exception as e:
                        if "Ошибка от LM Studio" in str(e):
                            raise e
                        pass
        except Exception as e:
            yield f"\n[!] Ошибка генерации ответа LLM: {e}\nУбедитесь, что сервер LM Studio запущен на порту {api_base} и контекстное окно модели достаточно для объема запроса."

    def translate_text(self, text: str, target_lang: str) -> str:
        """
        Translates a given text into target_lang (e.g. 'en', 'ru', 'de') using the local LLM.
        """
        api_base = self.config_mgr.get("LM_STUDIO_API_BASE", "http://localhost:1234/v1")
        api_url = f"{api_base.rstrip('/')}/chat/completions"
        model_name = self._get_loaded_model_name()
        
        # Select prompt based on target language for better local model alignment
        # We merge instructions and content into a single user message because small models
        # (like Qwen 4b) follow instructions in user prompts much better than in system prompts.
        if target_lang.lower() == "ru":
            prompt_content = (
                "Ты — профессиональный технический переводчик.\n"
                "Переведи предоставленный ниже текст на русский язык.\n"
                "Правила:\n"
                "1. Выведи ТОЛЬКО переведенный текст. Никаких примечаний, вступлений, пояснений или markdown-оформления (кроме оригинального).\n"
                "2. Сохраняй неизменными технические коды ошибок (например, C-2201), названия деталей и оригинальное форматирование.\n\n"
                f"Текст для перевода:\n{text}"
            )
        else:
            lang_names_en = {
                "en": "English",
                "de": "German",
                "fr": "French",
                "es": "Spanish",
                "it": "Italian",
                "ja": "Japanese",
                "zh": "Chinese",
                "ko": "Korean",
                "tr": "Turkish"
            }
            lang_name = lang_names_en.get(target_lang.lower(), target_lang)
            prompt_content = (
                "You are a professional technical translator.\n"
                f"Translate the provided text below into the target language: {lang_name}.\n"
                "Strict rules:\n"
                "1. Output ONLY the translated text. Do not add comments, greetings, explanations, or extra markdown formatting.\n"
                "2. Preserve original formatting, line breaks, and technical codes (like C-2201) exactly.\n\n"
                f"Text to translate:\n{text}"
            )
        
        payload = {
            "model": model_name,
            "messages": [
                {"role": "user", "content": prompt_content}
            ],
            "temperature": 0.2,
            "max_tokens": 1500,
            "stream": False
        }
        
        print(f"[*] API Base: {api_base}")
        print(f"[*] Target model: {model_name}")
        print(f"[*] Payload sent to LM Studio: {json.dumps(payload, ensure_ascii=False)[:300]}...")
        
        try:
            response = requests.post(api_url, json=payload, timeout=90)
            response.raise_for_status()
            data = response.json()
            print(f"[*] LM Studio API Response Status: {response.status_code}")
            print(f"[*] LM Studio API Response Snippet: {json.dumps(data, ensure_ascii=False)[:300]}...")
            
            message_data = data.get("choices", [{}])[0].get("message", {})
            translation = message_data.get("content", "")
            # Support reasoning-focused models that put output in reasoning_content
            if not translation:
                translation = message_data.get("reasoning_content", "")
            
            translation = translation.strip()
            if translation:
                return translation
            raise Exception("Empty response from LLM (both content and reasoning_content are empty)")
        except Exception as e:
            print(f"[!] Translation error: {e}")
            return f"[Error translating text: {e}]"
