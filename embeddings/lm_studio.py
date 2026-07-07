# embeddings/lm_studio.py
import requests
import config
from embeddings.base import BaseEmbeddings

class LMStudioEmbeddings(BaseEmbeddings):
    def __init__(self):
        self.api_url = f"{config.LM_STUDIO_API_BASE.rstrip('/')}/embeddings"
        self.model = config.EMBEDDING_MODEL
        
    def embed_documents(self, texts):
        try:
            response = requests.post(
                self.api_url,
                json={"model": self.model, "input": texts},
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            # OpenAI specification: results are in 'data', each having 'embedding' and 'index'
            sorted_data = sorted(data["data"], key=lambda x: x.get("index", 0))
            return [x["embedding"] for x in sorted_data]
        except Exception as e:
            print(f"[!] Error calling LM Studio Embeddings: {e}")
            print("[*] Falling back to MockEmbeddings to continue.")
            from embeddings.mock import MockEmbeddings
            return MockEmbeddings().embed_documents(texts)
            
    def embed_query(self, text):
        try:
            response = requests.post(
                self.api_url,
                json={"model": self.model, "input": text},
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]
        except Exception as e:
            print(f"[!] Error calling LM Studio Embeddings: {e}")
            print("[*] Falling back to MockEmbeddings to continue.")
            from embeddings.mock import MockEmbeddings
            return MockEmbeddings().embed_query(text)
