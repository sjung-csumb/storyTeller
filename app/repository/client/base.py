#app/repository/client/base.py
from abc import ABC, abstractmethod

class BaseClient(ABC):
    @abstractmethod
    def get_chat_model(self):
        pass

    @abstractmethod
    def get_embedding_model(self):
        pass