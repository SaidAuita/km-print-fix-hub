# embeddings/huggingface.py
import requests
import config
from embeddings.base import BaseEmbeddings

class HuggingFaceEmbeddings(BaseEmbeddings):
    def __init__(self):
        self.model = config.EMBEDDING_MODEL
        if "/" in self.model:
            self.api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{self.model}"
        else:
            self.api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/{self.model}"
            
    def _call_api(self, payload):
        headers = {}
        if getattr(config, 'HUGGINGFACE_API_KEY', ''):
            headers["Authorization"] = f"Bearer {config.HUGGINGFACE_API_KEY}"
        
        response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()

    def embed_documents(self, texts):
        try:
            res = self._call_api({"inputs": texts, "options": {"wait_for_model": True}})
            return res
        except Exception as e:
            print(f"[!] Error calling Hugging Face Inference API: {e}")
            print("[*] Falling back to MockEmbeddings.")
            from embeddings.mock import MockEmbeddings
            return MockEmbeddings().embed_documents(texts)
            
    def embed_query(self, text):
        try:
            res = self._call_api({"inputs": text, "options": {"wait_for_model": True}})
            if isinstance(res, list) and len(res) > 0:
                if isinstance(res[0], float):
                    return res
                elif isinstance(res[0], list):
                    return res[0]
            return res
        except Exception as e:
            print(f"[!] Error calling Hugging Face Inference API: {e}")
            print("[*] Falling back to MockEmbeddings.")
            from embeddings.mock import MockEmbeddings
            return MockEmbeddings().embed_query(text)
