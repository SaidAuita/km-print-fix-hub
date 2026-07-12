# embeddings/ollama.py
import requests
import config
from embeddings.base import BaseEmbeddings

class OllamaEmbeddings(BaseEmbeddings):
    def __init__(self):
        from config.manager import ConfigManager
        config_mgr = ConfigManager()
        api_base = config_mgr.get("OLLAMA_API_BASE", "http://localhost:11434/v1")
        
        # Strip trailing slashes and normalize base
        api_base_clean = api_base.rstrip('/')
        
        # Base url for native Ollama API (without /v1)
        if api_base_clean.endswith("/v1"):
            self.native_base = api_base_clean[:-3].rstrip('/')
            self.openai_url = f"{api_base_clean}/embeddings"
        else:
            self.native_base = api_base_clean
            self.openai_url = f"{api_base_clean}/v1/embeddings"
            
        self.native_embeddings_url = f"{self.native_base}/api/embeddings"
        self.native_embed_url = f"{self.native_base}/api/embed"
        
        self.model = config_mgr.get("EMBEDDING_MODEL", config.EMBEDDING_MODEL)

    def _embed_openai_style(self, texts):
        payload = {"model": self.model, "input": texts}
        response = requests.post(self.openai_url, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        sorted_data = sorted(data["data"], key=lambda x: x.get("index", 0))
        return [x["embedding"] for x in sorted_data]

    def _embed_native_embed(self, texts):
        payload = {"model": self.model, "input": texts}
        response = requests.post(self.native_embed_url, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()["embeddings"]

    def _embed_native_embeddings(self, text):
        payload = {"model": self.model, "prompt": text}
        response = requests.post(self.native_embeddings_url, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()["embedding"]

    def embed_documents(self, texts):
        # Try OpenAI-compatible endpoint first
        try:
            return self._embed_openai_style(texts)
        except Exception as e1:
            print(f"[*] OpenAI-compatible embedding failed, trying native /api/embed: {e1}")
            
        # Try native /api/embed
        try:
            return self._embed_native_embed(texts)
        except Exception as e2:
            print(f"[*] Native /api/embed failed, falling back to sequential /api/embeddings: {e2}")
            
        # Fallback to sequential /api/embeddings
        try:
            embeddings = []
            for text in texts:
                embeddings.append(self._embed_native_embeddings(text))
            return embeddings
        except Exception as e3:
            print(f"[!] All embedding attempts failed: {e3}")
            print("[*] Falling back to MockEmbeddings to continue.")
            from embeddings.mock import MockEmbeddings
            return MockEmbeddings().embed_documents(texts)

    def embed_query(self, text):
        # Try OpenAI-compatible endpoint first
        try:
            res = self._embed_openai_style([text])
            if res:
                return res[0]
        except Exception as e1:
            print(f"[*] OpenAI-compatible query embedding failed, trying native /api/embed: {e1}")
            
        # Try native /api/embed
        try:
            res = self._embed_native_embed([text])
            if res:
                return res[0]
        except Exception as e2:
            print(f"[*] Native query /api/embed failed, trying native /api/embeddings: {e2}")
            
        # Try native /api/embeddings
        try:
            return self._embed_native_embeddings(text)
        except Exception as e3:
            print(f"[!] All query embedding attempts failed: {e3}")
            print("[*] Falling back to MockEmbeddings to continue.")
            from embeddings.mock import MockEmbeddings
            return MockEmbeddings().embed_query(text)
