# embeddings/factory.py
import config

def get_embeddings_provider(provider=None):
    """
    Factory function to instantiate and return the configured embedding provider.
    """
    if provider is None:
        provider = getattr(config, 'EMBEDDING_PROVIDER', 'mock')
        
    provider_clean = provider.lower().strip()
    
    if provider_clean == "sentence-transformers":
        from embeddings.sentence_transformers import SentenceTransformersEmbeddings
        return SentenceTransformersEmbeddings()
    elif provider_clean == "lm-studio":
        from embeddings.lm_studio import LMStudioEmbeddings
        return LMStudioEmbeddings()
    elif provider_clean == "ollama":
        from embeddings.ollama import OllamaEmbeddings
        return OllamaEmbeddings()
    elif provider_clean == "huggingface":
        from embeddings.huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings()
    else:
        from embeddings.mock import MockEmbeddings
        return MockEmbeddings()
