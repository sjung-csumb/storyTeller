#app/repository/client/llm_client.py
import os
from langchain_upstage import ChatUpstage, UpstageEmbeddings
from dotenv import load_dotenv
from app.repository.client.base import BaseLLMClient

load_dotenv(override=False)

class UpstageClient(BaseLLMClient):
    def __init__(self):
        self.api_key = os.getenv("UPSTAGE_API_KEY")
        self.chat_model_name = os.getenv("UPSTAGE_CHAT_MODEL","solor-pro2")
        self.embedding_model_name = os.getenv("UPSTAGE_EMBEDDING_MODEL","solor-embbeding-1-large")
        self._chat_instance = None
        self._embedding_instance = None

    def get_chat_model(self) -> ChatUpstage:
        if self._chat_instance is None:
            self._chat_instance = ChatUpstage(
                api_key=self.api_key,
                model_name=self.chat_model_name
            )
        return self._chat_instance

    def get_embedding_model(self) -> UpstageEmbeddings:
        if self._embedding_instance is None:
            self._embedding_instance = UpstageEmbeddings(
                api_key=self.api_key,
                model=self.embedding_model_name
            )
        return self._embedding_instance