from app.repositories import SignRepository
from app.domains.models import *
from .exceptions import *
from app.settings import Settings
from dataclasses import dataclass
import bcrypt
import re

class SignService:
    def __init__(self, repo: SignRepository, settings: Settings):
        self.repo = repo
        self.settings = settings

    #TODO: Надо изменить repo, чтобы не было методов по типу checkUserEmailExistence, а только для чтения и записи

    async def signUp(self, data: SignUpData):
        #TODO: Проверить корректность email
        if not bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', data.email)):
            raise InvalidEmail("Некорректный формат email")
        if await self.repo.checkUserEmailExistence(data.email):
            raise EmailIsBusy()
        try:
            hashed_password: bytes = bcrypt.hashpw(data.password.encode(), self.settings.PASSWORD_HASH_SALT.encode())
            await self.repo.insertAccount(AccountData(email=data.email, hashed_password=hashed_password))
        except:
            #TODO: logger
            print("Cannot insert sign")


    async def signIn(self, request: SignRequest)->AuthToken:
        try:
            request.password = bcrypt.hashpw(request.password.encode(), self.settings.PASSWORD_HASH_SALT.encode()).decode()
            data: AuthToken = await self.repo.findAccount(request)
        except:
            raise IncorrectEmailOrPassword()
        return data

    #TODO: Далее, возможно всё-таки стоит для чтения сделать отдельный AuthService для получения информации о том, что может сделать пользователь 
