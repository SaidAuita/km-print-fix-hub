import os
import config
from embeddings.base import BaseEmbeddings

# Используем зеркало Hugging Face для надежной и быстрой загрузки моделей в РФ
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

class SentenceTransformersEmbeddings(BaseEmbeddings):
    def __init__(self):
        # Check if local offline model cache exists in the embeddings folder
        local_cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model_cache")
        if os.path.exists(local_cache_path) and os.path.exists(os.path.join(local_cache_path, "model.safetensors")):
            self.model_name = local_cache_path
            print(f"[*] Loading local offline sentence-transformers model from: {self.model_name}")
        else:
            self.model_name = config.EMBEDDING_MODEL
            print(f"[*] Loading sentence-transformers model from HF/cache: {self.model_name}")
            
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
        except Exception as e:
            print(f"[!] Error loading sentence-transformers model '{self.model_name}': {e}")
            print("[*] Falling back to MockEmbeddings for this session.")
            self.model = None
            
    def embed_documents(self, texts):
        if self.model is None:
            from embeddings.mock import MockEmbeddings
            return MockEmbeddings().embed_documents(texts)
        embeddings = self.model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()
        
    def embed_query(self, text):
        if self.model is None:
            from embeddings.mock import MockEmbeddings
            return MockEmbeddings().embed_query(text)
        embedding = self.model.encode(text)
        return embedding.tolist()

    def is_mock(self):
        return self.model is None
