# embeddings/mock.py
import hashlib
import numpy as np
from embeddings.base import BaseEmbeddings

class MockEmbeddings(BaseEmbeddings):
    def __init__(self, dimension=384):
        self.dimension = dimension
        
    def _get_stable_vector(self, text):
        sha = hashlib.sha256(text.encode('utf-8')).digest()
        # Seed generator deterministically based on text hash
        seed = int.from_bytes(sha[:4], byteorder='big')
        rng = np.random.default_rng(seed)
        vec = rng.normal(size=self.dimension)
        # Normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def embed_documents(self, texts):
        return [self._get_stable_vector(t) for t in texts]
        
    def embed_query(self, text):
        return self._get_stable_vector(text)

    def is_mock(self):
        return True
