# from langchain_core.language_models.chat_models import BaseChatModel
# from langchain_upstage import ChatUpstage

# # 강의 노트북과 동일한 모델명 사용
# MODEL = "solar-pro2"


# def get_llm(temperature: float = 0.0, model: str | None = None) -> BaseChatModel:
#     """Upstage Solar LLM 클라이언트를 생성한다.

#     api_key는 환경변수 UPSTAGE_API_KEY에서 자동으로 읽어온다.
#     """
#     return ChatUpstage(model=model or MODEL, temperature=temperature)
#app/core/llm.py
from app.repository.client.llm_client import UpstageClient

_client = UpstageClient()

def get_solar_chat():
    return _client.get_chat_model()

def get_upstage_embeddings():
    return _client.get_embedding_model()

