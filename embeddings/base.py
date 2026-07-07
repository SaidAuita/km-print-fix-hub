# embeddings/base.py
from abc import ABC, abstractmethod

class BaseEmbeddings(ABC):
    @abstractmethod
    def embed_documents(self, texts):
        """
        Embeds a list of text documents.
        Returns a list of float lists (embeddings).
        """
        pass
        
    @abstractmethod
    def embed_query(self, text):
        """
        Embeds a single query text.
        Returns a float list.
        """
        pass

    def is_mock(self):
        return False
