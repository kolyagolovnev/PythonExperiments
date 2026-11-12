from abc import ABC, abstractmethod
from typing import Optional, List

from app.domains.models import *

class SignRepository(ABC):
    @abstractmethod
    async def checkUserEmailExistence(self, email: str)->bool:
        pass #TODO

    @abstractmethod
    async def insertAccount(self, account: AccountData):
        pass #TODO

    @abstractmethod
    async def findAccount(self, sign: SignRequest)->AuthToken:
        pass #TODO

class AuthRepository(ABC):
    pass

class UserRepository(ABC):
    @abstractmethod
    async def add_user(self, user: User):
        pass

    @abstractmethod
    async def get_user(self, user_id: int)->User:
        pass

    @abstractmethod
    async def update_user(self, user: User):
        pass

    @abstractmethod
    async def delete_user(self, user_id: int):
        pass

    @abstractmethod
    async def select_users_short(self, search_params: UserSearchParams)->List[UserListItem]:
        pass

class GroupRepository(ABC):
    @abstractmethod
    async def addGroup(self, group: Group):
        pass
    #TODO: Дргие методы групп

class PasteRepository(ABC):
    @abstractmethod
    async def addPaste(self, paste: Paste):
        pass

    @abstractmethod
    async def deletePaste(self, paste_id: int):
        pass

    @abstractmethod
    async def getPastes(self):
        pass