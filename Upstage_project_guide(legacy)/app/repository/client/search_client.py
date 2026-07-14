# app/repository/client/search_client.py
import os
from langchain_community.utilities import GoogleSerperAPIWrapper
from app.repository.client.base import BaseSearchClient
from dotenv import load_dotenv
# .env 파일이 있으면 로드하고, 없으면 주입된 환경변수를 사용합니다.
load_dotenv(override=False)
class SerperSearchClient(BaseSearchClient):
    def __init__(self):
        # langchain의 유틸리티 래퍼를 사용하여 간편하게 구현
        self._search = GoogleSerperAPIWrapper()

    def search(self, query: str) -> str:
        return self._search.run(query)