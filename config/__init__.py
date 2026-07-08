# config/__init__.py
# Настройки конфигурации для Trade-Print RAG системы.

# The starting forum section URL to scrape
FORUM_URL = "https://forum.trade-print.ru/forumdisplay.php?f=13"
TRADEPRINT_URL = FORUM_URL
COLORPRINTING_URL = "https://www.colorprintingforum.com/community/konica-minolta-color-laser-printer-color-copier/"
PRINTPLANET_URL = "https://printplanet.com/forums/digital-printing-discussion.37/"
COPYTECHNET_URL = "https://www.copytechnet.com/forum/tech-support/konica-minolta/"

# The output folder path where raw HTML files and parsed JSONs are stored
ARCHIVE_DIR = "Archive"

# HTTP headers to mimic a normal browser request
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Delay in seconds between requests to avoid rate limits or IP blocking
REQUEST_DELAY = 1.5

# Number of attempts for request retries in case of network or server failures
MAX_RETRIES = 3

# HTTP request timeout in seconds
TIMEOUT = 15

# =====================================================================
# Stage 2: Knowledge Base & Vector Indexing Configurations
# =====================================================================

# Chunking settings
CHUNK_SIZE_WORDS = 600       # Target word count per discussion chunk
CHUNK_OVERLAP_POSTS = 1      # Number of overlapping posts between consecutive chunks
INCLUDE_QUOTES_IN_INDEX = True  # Whether to append quoted text to indexed chunks

# Embeddings settings
# Supported providers: "sentence-transformers", "lm-studio", "huggingface", "mock"
EMBEDDING_PROVIDER = "sentence-transformers"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
LM_STUDIO_API_BASE = "http://localhost:1234/v1"
HUGGINGFACE_API_KEY = ""

# Vector store settings
# Supported types: "simple" (NumPy based, no dependencies), "faiss"
VECTOR_STORE_TYPE = "simple"
INDEX_DIR = "Index"
SEARCH_RESULTS_COUNT = 10

# =====================================================================
# Stage 3: Web App, Search Coordinator & LLM Settings
# =====================================================================
WEB_HOST = "127.0.0.1"
WEB_PORT = 8000
SETTINGS_FILE = "settings.json"

# Reranking & Search counts
FTS_RESULTS_COUNT = 40
VECTOR_RESULTS_COUNT = 40
RERANKED_RESULTS_COUNT = 12  # Number of final documents passed to LLM
MAX_CONTEXT_SIZE_WORDS = 4000

# LLM Generation settings
SYSTEM_PROMPT_RU = (
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
)

SYSTEM_PROMPT_EN = (
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
)

LAST_LANG = "ru"
LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 2048

def load_models_list():
    import os
    default_models = [
        "C14010", "C14010S", "C12010", "C12010S", "C10500", "C10500S",
        "C14000", "C12000", "C6100", "C6085", "C4080", "C4070", "C4065", "C3080", "C3070", "C2070", "C2060",
        "C1070", "C1060", "C8000", "C7000", "C6000", "C6501", "C5501", "C6500", "C5500", "C250I", "C300I",
        "C360I", "C258", "C308", "C368", "C224", "C284", "C364", "C220", "C280", "C360", "C452", "C451", "C353",
        "1250", "1200", "1050", "1100"
    ]
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(base_dir, "models_list.txt")
    
    if not os.path.exists(file_path):
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("# KM Print Fix Hub - Supported Models List / Список поддерживаемых моделей\n")
                f.write("# You can add or edit model names below (one per line)\n")
                f.write("# Вы можете добавлять или редактировать названия моделей (по одной на строке)\n\n")
                for m in default_models:
                    f.write(f"{m}\n")
        except Exception:
            pass
            
    if os.path.exists(file_path):
        try:
            models = []
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        models.append(line)
            if models:
                return models
        except Exception:
            pass
            
    return default_models
