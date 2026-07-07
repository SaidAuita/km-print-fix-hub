# vector_store/factory.py
import config

def get_vector_store(store_type=None):
    """
    Factory function to instantiate and return the configured vector store.
    """
    if store_type is None:
        store_type = getattr(config, 'VECTOR_STORE_TYPE', 'simple')
        
    store_clean = store_type.lower().strip()
    
    if store_clean == "faiss":
        from vector_store.faiss_store import FaissVectorStore
        return FaissVectorStore()
    else:
        from vector_store.simple_store import SimpleVectorStore
        return SimpleVectorStore()
