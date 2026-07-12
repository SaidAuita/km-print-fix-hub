#!/usr/bin/env python3
# chat_rag.py
# Консольный RAG-чат для поиска по базе знаний форума и генерации ответов через LM Studio API.

import os
import sys
import json
import requests
import config
from search.searcher import Searcher

# Настройки RAG
NUM_RETRIEVED_CHUNKS = 4  # Количество чанков форума для передачи в контекст LLM

from config.manager import ConfigManager
config_mgr = ConfigManager()

def get_api_base():
    provider = config_mgr.get("LLM_PROVIDER", config_mgr.get("provider", "lmstudio"))
    providers = config_mgr.get("LLM_PROVIDERS", config_mgr.get("providers", {}))
    if isinstance(providers, dict) and provider in providers:
        url = providers[provider].get("url")
        if url:
            return url
    if provider == "ollama":
        return config_mgr.get("OLLAMA_API_BASE", "http://localhost:11434/v1")
    return config_mgr.get("LM_STUDIO_API_BASE", "http://localhost:1234/v1")

def get_loaded_model_name():
    """
    Запрашивает у LM Studio или Ollama список загруженных моделей.
    Возвращает имя первой загруженной модели или дефолтное значение.
    """
    api_base = get_api_base()
    models_url = f"{api_base.rstrip('/')}/models"
    try:
        response = requests.get(models_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = data.get("data", [])
            if models:
                # Возвращаем ID первой загруженной модели
                return models[0].get("id")
    except Exception:
        pass
    return "google/gemma-4-12b-qat"

def get_model_name():
    configured_model = config_mgr.get("LLM_MODEL")
    if configured_model:
        return configured_model
    return get_loaded_model_name()

def build_prompt(query, search_results):
    """
    Формирует контекст из результатов поиска и строит промпт для LLM.
    """
    context_parts = []
    sources = []
    
    for idx, (doc, score) in enumerate(search_results, 1):
        thread_title = doc.get("thread_title", "Без названия")
        url = doc.get("url", "Нет ссылки")
        text = doc.get("text", "")
        
        # Запоминаем источник для вывода пользователю
        sources.append({
            "idx": idx,
            "title": thread_title,
            "url": url,
            "score": score,
            "authors": doc.get("metadata", {}).get("authors", []),
            "posts": doc.get("metadata", {}).get("post_numbers", [])
        })
        
        # Форматируем текст чанка для LLM
        chunk_content = (
            f"--- ИСТОЧНИК №{idx} ---\n"
            f"Тема: {thread_title}\n"
            f"Ссылка: {url}\n"
            f"Содержание обсуждения:\n{text}\n"
            f"-----------------------\n"
        )
        context_parts.append(chunk_content)
        
    context_text = "\n\n".join(context_parts)
    
    system_prompt = (
        "Ты — опытный инженер технической поддержки форума полиграфистов Trade-Print.\n"
        "Твоя задача — отвечать на вопросы пользователей по проблемам печати, эксплуатации и ремонта печатного оборудования (Konica Minolta, Xerox, Epson и др.), используя ТОЛЬКО предоставленные фрагменты обсуждений с форума (Контекст).\n\n"
        "Правила ответа:\n"
        "1. Отвечай на русском языке, технически грамотно и структурировано (используй списки, абзацы).\n"
        "2. Основывай свой ответ строго на фактах и решениях из предоставленного Контекста.\n"
        "3. Если предоставленный Контекст не содержит ответа на вопрос или информации недостаточно, честно ответь, что на форуме не найдено обсуждений по этой конкретной проблеме, но можешь дать общие рекомендации на основе твоих знаний, четко разграничив информацию с форума и общие советы.\n"
        "4. В конце своего ответа кратко перечисли номера источников (например, [1], [2]), на которые ты опирался."
    )
    
    user_prompt = (
        f"КОНТЕКСТ С ФОРУМА TRADE-PRINT:\n"
        f"==================================================\n"
        f"{context_text}\n"
        f"==================================================\n\n"
        f"ВОПРОС ПОЛЬЗОВАТЕЛЯ: {query}\n\n"
        f"Дай развернутый ответ на основе предоставленного Контекста:"
    )
    
    return system_prompt, user_prompt, sources

def ask_llm(system_prompt, user_prompt, model_name):
    """
    Отправляет запрос к LLM (LM Studio / Ollama) с поддержкой потокового вывода (streaming).
    """
    api_base = get_api_base()
    api_url = f"{api_base.rstrip('/')}/chat/completions"
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": config_mgr.get("LLM_TEMPERATURE", 0.3),
        "stream": True
    }
    
    try:
        response = requests.post(api_url, json=payload, stream=True, timeout=900)
        response.raise_for_status()
        
        print("\nОтвет модели:\n" + "-"*80)
        
        full_response = ""
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
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        print(content, end="", flush=True)
                        full_response += content
                except json.JSONDecodeError:
                    pass
        print("\n" + "-"*80)
        return True
    except requests.exceptions.RequestException as e:
        provider = config_mgr.get("LLM_PROVIDER", "lmstudio")
        provider_name = "Ollama" if provider == "ollama" else "LM Studio"
        print(f"\n[!] Ошибка связи с API {provider_name}: {e}")
        print(f"[*] Убедитесь, что сервер {provider_name} запущен по адресу {api_base}.")
        return False

def main():
    index_dir = getattr(config, 'INDEX_DIR', 'Index')
    if not os.path.exists(index_dir):
        print(f"[!] Ошибка: Индекс базы знаний '{index_dir}' не найден.")
        print("[*] Пожалуйста, сначала сгенерируйте индекс: python index_kb.py")
        sys.exit(1)
        
    print("[*] Загрузка векторного индекса форума...")
    try:
        searcher = Searcher()
    except Exception as e:
        print(f"[!] Ошибка инициализации поисковика: {e}")
        sys.exit(1)
        
    provider = config_mgr.get("LLM_PROVIDER", "lmstudio")
    provider_name = "Ollama" if provider == "ollama" else "LM Studio"
    print(f"[*] Подключение к {provider_name}...")
    model_name = get_model_name()
    print(f"[+] Имя активной модели в {provider_name}: {model_name}")
    print("[+] RAG-чат готов к работе!")
    print("Задайте свой вопрос по проблемам печати (или введите 'exit' для выхода):")
    print("=" * 80)
    
    while True:
        try:
            query = input("\nВопрос: ").strip()
            if not query:
                continue
            if query.lower() in ['exit', 'quit', 'выход']:
                print("До свидания!")
                break
                
            print("[*] Поиск подходящих тем на форуме...")
            # Поиск документов по вопросу
            search_results = searcher.search(query, k=NUM_RETRIEVED_CHUNKS)
            
            if not search_results:
                print("[-] В базе данных форума не найдено тем, похожих на ваш вопрос.")
                continue
                
            # Формирование промпта и получение списка источников
            system_prompt, user_prompt, sources = build_prompt(query, search_results)
            
            # Запрос к LLM в LM Studio
            success = ask_llm(system_prompt, user_prompt, model_name)
            
            if success:
                # Вывод источников с активными ссылками
                print("\nИспользуемые источники с форума:")
                for src in sources:
                    authors_str = f" (авторы: {', '.join(src['authors'])})" if src['authors'] else ""
                    posts_str = f" [посты: {', '.join(src['posts'])}]" if src['posts'] else ""
                    print(f"[{src['idx']}] Тема: \"{src['title']}\"")
                    print(f"    Ссылка: {src['url']}{posts_str}{authors_str}")
                    print(f"    Релевантность (score): {src['score']:.4f}")
                print("=" * 80)
                
        except KeyboardInterrupt:
            print("\nВыход из чата. До свидания!")
            break
        except Exception as e:
            print(f"[!] Произошла ошибка: {e}")

if __name__ == "__main__":
    main()
