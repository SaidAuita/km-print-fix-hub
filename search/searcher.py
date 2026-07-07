# search/searcher.py
import config
from embeddings.factory import get_embeddings_provider
from vector_store.factory import get_vector_store

class Searcher:
    def __init__(self, index_dir=None):
        if index_dir is None:
            self.index_dir = getattr(config, 'INDEX_DIR', 'Index')
        else:
            self.index_dir = index_dir
            
        # Instantiate embeddings provider
        self.embeddings = get_embeddings_provider()
        
        # Instantiate and load vector store
        self.vector_store = get_vector_store()
        self.vector_store.load(self.index_dir)
        
    def search(self, query_text, k=None):
        """
        Embeds the query text and performs similarity search in the index.
        Returns a list of tuples: (document_dict, similarity_score)
        """
        if k is None:
            k = getattr(config, 'SEARCH_RESULTS_COUNT', 10)
            
        # Generate embedding for the query
        query_vector = self.embeddings.embed_query(query_text)
        
        # Perform similarity search
        return self.vector_store.similarity_search(query_vector, k=k)
