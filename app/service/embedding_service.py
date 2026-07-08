#app/service/embbedding_service.py
import os
from typing import List
from openai import OpenAI
from dotenv import load_dotenv

from app.core.llm import get_upstage_embeddings

class EmbeddingService:
    def __init__(self):
        self._embddings = get_upstage_embeddings()
    def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """주어진 텍스트 리스트에 대한 임베딩을 생성한다.

        Args:
            texts (List[str]): 임베딩을 생성할 텍스트 리스트

        Returns:
            List[List[float]]: 각 텍스트에 대한 임베딩 벡터 리스트
        """
        return self._embeddings.embed_documents(texts)
    def create_embedding(self, text:str) -> List[float]:
        return self._embeddings.embed_query(text)