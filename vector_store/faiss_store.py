# vector_store/faiss_store.py
import os
import pickle
import numpy as np
from vector_store.base import BaseVectorStore

class FaissVectorStore(BaseVectorStore):
    def __init__(self):
        self.documents = []
        self.index = None
        self.dimension = None
        self.fallback_store = None
        
    def add_documents(self, documents, embeddings):
        if not documents:
            return
            
        try:
            import faiss
        except ImportError:
            print("[!] Error: 'faiss' package is not installed.")
            print("[*] Falling back to SimpleVectorStore logic.")
            from vector_store.simple_store import SimpleVectorStore
            self.fallback_store = SimpleVectorStore()
            self.fallback_store.add_documents(documents, embeddings)
            self.index = "fallback"
            return
            
        self.documents.extend(documents)
        embs = np.array(embeddings, dtype=np.float32)
        
        if self.dimension is None:
            self.dimension = embs.shape[1]
            # Use Inner Product index (corresponds to cosine similarity when vectors are normalized)
            self.index = faiss.IndexFlatIP(self.dimension)
            
        # L2 normalize embeddings for cosine similarity
        faiss.normalize_L2(embs)
        self.index.add(embs)
        
    def save(self, directory_path):
        os.makedirs(directory_path, exist_ok=True)
        if self.index == "fallback":
            self.fallback_store.save(directory_path)
            return
            
        try:
            import faiss
            faiss.write_index(self.index, os.path.join(directory_path, "faiss.index"))
            with open(os.path.join(directory_path, "faiss_docs.pkl"), "wb") as f:
                pickle.dump(self.documents, f)
        except Exception as e:
            print(f"[!] Error saving FAISS index: {e}")
            
    def load(self, directory_path):
        if os.path.exists(os.path.join(directory_path, "simple_store.pkl")):
            from vector_store.simple_store import SimpleVectorStore
            self.fallback_store = SimpleVectorStore()
            self.fallback_store.load(directory_path)
            self.index = "fallback"
            return
            
        try:
            import faiss
            self.index = faiss.read_index(os.path.join(directory_path, "faiss.index"))
            with open(os.path.join(directory_path, "faiss_docs.pkl"), "rb") as f:
                self.documents = pickle.load(f)
            self.dimension = self.index.d
        except Exception as e:
            raise FileNotFoundError(f"Error loading FAISS index: {e}")
            
    def similarity_search(self, query_vector, k=10):
        if self.index == "fallback":
            return self.fallback_store.similarity_search(query_vector, k)
            
        if self.index is None or not self.documents:
            return []
            
        try:
            import faiss
            q_vec = np.array([query_vector], dtype=np.float32)
            faiss.normalize_L2(q_vec)
            
            D, I = self.index.search(q_vec, k)
            
            results = []
            for score, idx in zip(D[0], I[0]):
                if idx != -1 and idx < len(self.documents):
                    results.append((self.documents[idx], float(score)))
            return results
        except Exception as e:
            print(f"[!] Error in FAISS similarity search: {e}")
            return []
