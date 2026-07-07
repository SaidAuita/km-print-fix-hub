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
