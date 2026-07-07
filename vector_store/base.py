# vector_store/base.py
from abc import ABC, abstractmethod

class BaseVectorStore(ABC):
    @abstractmethod
    def add_documents(self, documents, embeddings):
        """
        Adds a list of document objects and their corresponding embedding vectors.
        Each document is typically a dictionary:
        {
          "id": str,
          "thread_id": int,
          "thread_title": str,
          "url": str,
          "chunk_index": int,
          "text": str,
          "metadata": dict
        }
        """
        pass
        
    @abstractmethod
    def save(self, directory_path):
        """
        Serializes and saves the index files to the specified directory.
        """
        pass
        
    @abstractmethod
    def load(self, directory_path):
        """
        Loads the index files from the specified directory.
        """
        pass
        
    @abstractmethod
    def similarity_search(self, query_vector, k=10):
        """
        Searches the index with the query vector.
        Returns a list of tuples: (document_dict, similarity_score).
        """
        pass
