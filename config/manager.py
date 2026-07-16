# config/manager.py
# Менеджер динамических настроек для веб-приложения RAG.

import os
import json
import config

class ConfigManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(ConfigManager, cls).__new__(cls, *args, **kwargs)
            cls._instance._init_config()
        return cls._instance

    def _init_config(self):
        self.settings_file = getattr(config, 'SETTINGS_FILE', 'settings.json')
        self.defaults = {
            "EMBEDDING_PROVIDER": getattr(config, 'EMBEDDING_PROVIDER', 'mock'),
            "EMBEDDING_MODEL": getattr(config, 'EMBEDDING_MODEL', 'nomic-ai/nomic-embed-text-v1.5-GGUF'),
            "LLM_PROVIDER": getattr(config, 'LLM_PROVIDER', 'lmstudio'),
            "LLM_MODEL": getattr(config, 'LLM_MODEL', ''),
            "LM_STUDIO_API_BASE": getattr(config, 'LM_STUDIO_API_BASE', 'http://localhost:1234/v1'),
            "OLLAMA_API_BASE": getattr(config, 'OLLAMA_API_BASE', 'http://localhost:11434/v1'),
            "LLM_PROVIDERS": getattr(config, 'LLM_PROVIDERS', {
                "lmstudio": {"url": "http://localhost:1234/v1"},
                "ollama": {"url": "http://localhost:11434/v1"}
            }),
            "provider": getattr(config, 'provider', 'lmstudio'),
            "providers": getattr(config, 'providers', {
                "lmstudio": {"url": "http://localhost:1234/v1"},
                "ollama": {"url": "http://localhost:11434/v1"}
            }),
            "VECTOR_STORE_TYPE": getattr(config, 'VECTOR_STORE_TYPE', 'simple'),
            "COLORPRINTING_URL": getattr(config, 'COLORPRINTING_URL', 'https://www.colorprintingforum.com/community/konica-minolta-color-laser-printer-color-copier/'),
            "PRINTPLANET_URL": getattr(config, 'PRINTPLANET_URL', 'https://printplanet.com/forums/digital-printing-discussion.37/'),
            "COPYTECHNET_URL": getattr(config, 'COPYTECHNET_URL', 'https://www.copytechnet.com/forum/tech-support/konica-minolta/'),
            "INDEX_DIR": getattr(config, 'INDEX_DIR', 'Index'),
            "FTS_RESULTS_COUNT": getattr(config, 'FTS_RESULTS_COUNT', 25),
            "VECTOR_RESULTS_COUNT": getattr(config, 'VECTOR_RESULTS_COUNT', 25),
            "RERANKED_RESULTS_COUNT": getattr(config, 'RERANKED_RESULTS_COUNT', 10),
            "MAX_CONTEXT_SIZE_WORDS": getattr(config, 'MAX_CONTEXT_SIZE_WORDS', 3000),
            "LLM_CONTEXT_QUALITY_WORDS": getattr(config, 'LLM_CONTEXT_QUALITY_WORDS', 4000),
            "LLM_CONTEXT_SPEED_WORDS": getattr(config, 'LLM_CONTEXT_SPEED_WORDS', 1000),
            "SYSTEM_PROMPT_RU": getattr(config, 'SYSTEM_PROMPT_RU', (
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
            )),
            "SYSTEM_PROMPT_EN": getattr(config, 'SYSTEM_PROMPT_EN', (
                "You are a Konica Minolta technical support engineer.\n"
                "Answer ONLY in English.\n"
                "Use ONLY the provided context.\n"
                "Forbidden:\n"
                "* combining different models into a single diagnosis\n"
                "* adding new causes outside the context\n"
                "* making generalizations between models without explicit indication\n\n"
                "If the information refers to another model — be sure to specify it.\n\n"
                "RESPONSE FORMAT:\n\n"
                "Conclusion:\n"
                "...\n\n"
                "Causes:\n"
                "...\n\n"
                "What to check:\n"
                "...\n\n"
                "Sources:\n"
                "* Model X"
            )),
            "SYSTEM_PROMPT_DE": getattr(config, 'SYSTEM_PROMPT_DE', (
                "Sie sind ein technischer Support-Ingenieur von Konica Minolta.\n"
                "Antworten Sie NUR auf Deutsch.\n"
                "Verwenden Sie NUR den bereitgestellten Kontext.\n"
                "Verboten:\n"
                "* Verschiedene Modelle in einer einzigen Diagnose kombinieren\n"
                "* Neue Ursachen außerhalb des Kontexts hinzufügen\n"
                "* Verallgemeinerungen zwischen Modellen ohne expliziten Hinweis vornehmen\n\n"
                "Wenn sich die Informationen auf ein anderes Modell beziehen, geben Sie dies unbedingt an.\n\n"
                "ANTWORTFORMAT:\n\n"
                "Fazit:\n"
                "...\n\n"
                "Ursachen:\n"
                "...\n\n"
                "Was zu prüfen ist:\n"
                "...\n\n"
                "Quellen:\n"
                "* Modell X"
            )),
            "SYSTEM_PROMPT_FR": getattr(config, 'SYSTEM_PROMPT_FR', (
                "Vous êtes un ingénieur du support technique Konica Minolta.\n"
                "Répondez UNIQUEMENT en français.\n"
                "Utilisez UNIQUEMENT le contexte fourni.\n"
                "Interdit:\n"
                "* combiner différents modèles dans un seul diagnostic\n"
                "* ajouter de nouvelles causes en dehors du contexte\n"
                "* faire des généralisations entre les modèles sans indication explicite\n\n"
                "Si les informations font référence à un autre modèle, veillez à le préciser.\n\n"
                "FORMAT DE RÉPONSE:\n\n"
                "Conclusion:\n"
                "...\n\n"
                "Causes:\n"
                "...\n\n"
                "Ce qu'il faut vérifier:\n"
                "...\n\n"
                "Sources:\n"
                "* Modèle X"
            )),
            "SYSTEM_PROMPT_ES": getattr(config, 'SYSTEM_PROMPT_ES', (
                "Usted es un ingeniero de soporte técnico de Konica Minolta.\n"
                "Responda ÚNICAMENTE en español.\n"
                "Utilice ÚNICAMENTE el contexto proporcionado.\n"
                "Prohibido:\n"
                "* combinar diferentes modelos en un solo diagnóstico\n"
                "* agregar nuevas causas fuera del contexto\n"
                "* hacer generalizaciones entre modelos sin indicación explícita\n\n"
                "Si la información se refiere a otro modelo, asegúrese de especificarlo.\n\n"
                "FORMATO DE RESPUESTA:\n\n"
                "Conclusión:\n"
                "...\n\n"
                "Causas:\n"
                "...\n\n"
                "Qué verificar:\n"
                "...\n\n"
                "Fuentes:\n"
                "* Modelo X"
            )),
            "SYSTEM_PROMPT_IT": getattr(config, 'SYSTEM_PROMPT_IT', (
                "Sei un ingegnere del supporto tecnico Konica Minolta.\n"
                "Rispondi SOLO in italiano.\n"
                "Usa SOLO il contesto fornito.\n"
                "Vietato:\n"
                "* combinare modelli diversi in un'unica diagnosi\n"
                "* aggiungere nuove cause al di fuori del contesto\n"
                "* fare generalizzazioni tra modelli senza indicazione esplicita\n\n"
                "Se le informazioni si riferiscono a un altro modello, assicurati di specificarlo.\n\n"
                "FORMATO DELLA RISPOSTA:\n\n"
                "Conclusione:\n"
                "...\n\n"
                "Cause:\n"
                "...\n\n"
                "Cosa controllare:\n"
                "...\n\n"
                "Fonti:\n"
                "* Modello X"
            )),
            "SYSTEM_PROMPT_ZH": getattr(config, 'SYSTEM_PROMPT_ZH', (
                "您是柯尼卡美能达技术支持工程师。\n"
                "请仅用中文回答。\n"
                "仅使用提供的上下文。\n"
                "禁止：\n"
                "* 将不同型号合并为一个诊断\n"
                "* 添加上下文之外的新原因\n"
                "* 在没有明确说明的情况下对不同型号进行概括\n\n"
                "如果信息指的是另一个型号，请务必注明。\n\n"
                "回答格式：\n\n"
                "结论：\n"
                "...\n\n"
                "原因：\n"
                "...\n\n"
                "需要检查：\n"
                "...\n\n"
                "来源：\n"
                "* 型号 X"
            )),
            "SYSTEM_PROMPT_JA": getattr(config, 'SYSTEM_PROMPT_JA', (
                "あなたはコニカミノルタのテクニカルサポートエンジニアです。\n"
                "日本語でのみ回答してください。\n"
                "提供されたコンテキストのみを使用してください。\n"
                "禁止事項：\n"
                "* 異なるモデルを単一の診断に組み合わせること\n"
                "* コンテキスト外の新しい原因を追加すること\n"
                "* 明示的な指示なしにモデル間で一般化を行うこと\n\n"
                "情報が別のモデルを参照している場合は、必ず指定してください。\n\n"
                "回答フォーマット：\n\n"
                "結論：\n"
                "...\n\n"
                "原因：\n"
                "...\n\n"
                "確認事項：\n"
                "...\n\n"
                "情報源：\n"
                "* モデル X"
            )),
            "SYSTEM_PROMPT_PT": getattr(config, 'SYSTEM_PROMPT_PT', (
                "Você é um engenheiro de suporte técnico da Konica Minolta.\n"
                "Responda APENAS em português.\n"
                "Use APENAS o contexto fornecido.\n"
                "Proibido:\n"
                "* combinar modelos diferentes em um único diagnóstico\n"
                "* adicionar novas causas fora do contexto\n"
                "* fazer generalizações entre modelos sem indicação explícita\n\n"
                "Se a informação se referir a outro modelo, certifique-se de especificá-lo.\n\n"
                "FORMATO DE RESPOSTA:\n\n"
                "Conclusão:\n"
                "...\n\n"
                "Causas:\n"
                "...\n\n"
                "O que verificar:\n"
                "...\n\n"
                "Fontes:\n"
                "* Modelo X"
            )),
            "SYSTEM_PROMPT_TR": getattr(config, 'SYSTEM_PROMPT_TR', (
                "Siz bir Konica Minolta teknik destek mühendisiniz.\n"
                "SADECE Türkçe cevap verin.\n"
                "SADECE sağlanan bağlamı kullanın.\n"
                "Yasaklar:\n"
                "* Farklı modelleri tek bir teşhiste birleştirmek\n"
                "* Bağlam dışından yeni nedenler eklemek\n"
                "* Açık bir belirtim olmadan modeller arasında genelleme yapmak\n\n"
                "Eğer bilgi başka bir modele atıfta bulunuyorsa, bunu belirttiğinizden emin olun.\n\n"
                "CEVAP FORMATI:\n\n"
                "Sonuç:\n"
                "...\n\n"
                "Nedenler:\n"
                "...\n\n"
                "Kontrol edilecekler:\n"
                "...\n\n"
                "Kaynaklar:\n"
                "* Model X"
            )),
            "LLM_TEMPERATURE": getattr(config, 'LLM_TEMPERATURE', 0.3),
            "LLM_MAX_TOKENS": getattr(config, 'LLM_MAX_TOKENS', 2048),
            "LLM_CONTEXT_LENGTH": getattr(config, 'LLM_CONTEXT_LENGTH', 16000),
            "LLM_CONTEXT_MODE": getattr(config, 'LLM_CONTEXT_MODE', 'quality'),
            "WEB_HOST": getattr(config, 'WEB_HOST', '127.0.0.1'),
            "WEB_PORT": getattr(config, 'WEB_PORT', 8000),
            "ENABLE_CONTEXT_OPTIMIZER": getattr(config, 'ENABLE_CONTEXT_OPTIMIZER', False),
            "LAST_MODEL": "all",
            "LAST_SEARCH_MODE": "related",
            "LAST_SOURCE_FILTER": "auto",
            "LAST_STRICT_MODE": True,
            "LAST_SHOW_REASONING": False,
            "LAST_DEBUG_MODE": False,
            "LAST_ENABLE_CONTEXT_OPTIMIZER": False,
            "LAST_DIRECT_FORUM_LINKS": False,
            "LAST_CONTEXT_MODE": "quality",
            "LAST_LANG": getattr(config, 'LAST_LANG', 'ru'),
            "TRANSLATE_THREAD_TITLES": getattr(config, 'TRANSLATE_THREAD_TITLES', True),
            "LAST_TRANSLATE_THREAD_TITLES": True,
        }
        self.settings = {}
        self.load()

    def load(self):
        """Загружает настройки из settings.json, дополняя их дефолтными значениями."""
        self.settings = self.defaults.copy()
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    for k, v in saved.items():
                        # Преобразуем типы к оригинальным (для защиты от ошибок при вводе)
                        if k in self.defaults:
                            expected_type = type(self.defaults[k])
                            try:
                                self.settings[k] = expected_type(v)
                            except (ValueError, TypeError):
                                self.settings[k] = v
                        else:
                            self.settings[k] = v
            except Exception as e:
                print(f"[!] Ошибка загрузки settings.json: {e}")

    def save(self):
        """Сохраняет измененные настройки в settings.json."""
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[!] Ошибка сохранения settings.json: {e}")
            return False

    def get(self, key, default=None):
        """Получить значение настройки с динамическим маппингом SYSTEM_PROMPT."""
        if key == "SYSTEM_PROMPT":
            lang = self.settings.get("LAST_LANG", "ru")
            lang_key = f"SYSTEM_PROMPT_{lang.upper()}"
            if lang_key in self.settings:
                return self.settings[lang_key]
            if lang_key in self.defaults:
                return self.defaults[lang_key]
            return self.settings.get("SYSTEM_PROMPT_EN", self.defaults["SYSTEM_PROMPT_EN"])
        return self.settings.get(key, default)

    def set(self, key, value):
        """Изменить значение настройки (с поддержкой SYSTEM_PROMPT и проверкой типов)."""
        target_key = key
        if key == "SYSTEM_PROMPT":
            lang = self.settings.get("LAST_LANG", "ru")
            target_key = f"SYSTEM_PROMPT_{lang.upper()}"
            
        if target_key in self.defaults:
            expected_type = type(self.defaults[target_key])
            try:
                self.settings[target_key] = expected_type(value)
            except (ValueError, TypeError):
                self.settings[target_key] = value
        else:
            self.settings[target_key] = value

    def get_all(self):
        """Возвращает копию всех текущих настроек, включая динамически разрешенный SYSTEM_PROMPT."""
        res = self.settings.copy()
        res["SYSTEM_PROMPT"] = self.get("SYSTEM_PROMPT")
        return res
