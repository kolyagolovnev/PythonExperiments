from abc import ABC, abstractmethod
from typing import Optional, List

from domains.models import *

#TODO: SignRequest1 и SignRequest2, 2-е нужно в одну функцию свести регистрацию и авторизацию?
class SignRepository(ABC):
    @abstractmethod
    async def checkUserEmailExistence(self, email: str)->bool:
        pass #TODO

    @abstractmethod
    async def insertAccount(self, account: TempAccountData):
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
    async def get_user(self, user_id: int)->Optional[UserDTO]:
        pass

    @abstractmethod
    async def update_user(self, user: UserDTO):
        pass

    @abstractmethod
    async def delete_user(self, user_id: int):
        pass

    @abstractmethod
    async def select_users_short(self, search_params: UserSearchParams)->List[UserShort]:
        pass

class GroupRepository(ABC):
    @abstractmethod
    async def addGroup(self, group: GroupDTO):
        pass
    #TODO: Дргие методы групп

class PasteRepository(ABC):
    @abstractmethod
    async def addPaste(self, paste: PasteDTO):
        pass

    @abstractmethod
    async def deletePaste(self, paste_id: int):
        pass

    @abstractmethod
    async def getPastes(self):
        pass