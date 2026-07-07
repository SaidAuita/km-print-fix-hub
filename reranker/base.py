# reranker/base.py
# Базовый абстрактный класс для алгоритмов реранжирования.

from abc import ABC, abstractmethod

class BaseReranker(ABC):
    @abstractmethod
    def rerank(self, query_text, candidate_docs, k=10):
        """
        Реранжирует список кандидатов для заданного текстового запроса.
        
        :param query_text: Исходный текстовый запрос пользователя.
        :param candidate_docs: Список словарей документов (кандидатов).
        :param k: Количество финальных документов, которые нужно вернуть.
        :return: Список кортежей (document_dict, rerank_score), отсортированный по убыванию скора.
        """
        pass
