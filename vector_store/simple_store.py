# vector_store/simple_store.py
import os
import pickle
import numpy as np
from vector_store.base import BaseVectorStore

class SimpleVectorStore(BaseVectorStore):
    def __init__(self):
        self.documents = []
        self.embeddings = None  # NumPy array
        
    def add_documents(self, documents, embeddings):
        if not documents:
            return
        self.documents.extend(documents)
        new_embeddings = np.array(embeddings, dtype=np.float32)
        if self.embeddings is None:
            self.embeddings = new_embeddings
        else:
            self.embeddings = np.vstack([self.embeddings, new_embeddings])
            
    def save(self, directory_path):
        os.makedirs(directory_path, exist_ok=True)
        file_path = os.path.join(directory_path, "simple_store.pkl")
        with open(file_path, "wb") as f:
            pickle.dump({
                "documents": self.documents,
                "embeddings": self.embeddings
            }, f)
            
    def load(self, directory_path):
        file_path = os.path.join(directory_path, "simple_store.pkl")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"No simple store index found at {file_path}")
        with open(file_path, "rb") as f:
            data = pickle.load(f)
            self.documents = data["documents"]
            self.embeddings = data["embeddings"]
            
    def similarity_search(self, query_vector, k=10):
        if not self.documents or self.embeddings is None:
            return []
            
        q_vec = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []
            
        norms = np.linalg.norm(self.embeddings, axis=1)
        norms[norms == 0] = 1e-10  # Avoid division by zero
        
        dot_products = np.dot(self.embeddings, q_vec)
        similarities = dot_products / (norms * q_norm)
        
        # Sort indices descending
        top_k_indices = np.argsort(similarities)[::-1][:k]
        
        results = []
        for idx in top_k_indices:
            results.append((self.documents[idx], float(similarities[idx])))
        return results
