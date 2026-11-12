from abc import ABC, abstractmethod
from domains.models import *

class SignCacheRepository(ABC):
    #TODO: В репозитории должны быть только операции записи/чтения, вся логика проверки/вычислений должна быть в бизнес-логике

    @abstractmethod
    async def getTempAccount(self, email: str) -> TempAccountData:
        pass

    @abstractmethod
    async def addTempAccount(self, account_data: TempAccountData):
        pass