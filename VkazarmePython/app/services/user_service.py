from abc import ABC
from typing import Dict, List

from ..repositories import UserRepository 
from ..dto import UserDTO, UserCommand, Credentials
from .auth_service import AuthService
from .exceptions import *

 
#TODO: Нужно наверное конфигурацию из файла
#TODO: logger

class UserService:
    def __init__(self, repo: UserRepository, auth_service: AuthService):
        self.repo: UserRepository = repo
        self.auth_service = auth_service

    #TODO: тип credentials
    def addUser(user: UserDTO, credentials)->UserDTO:
        # TODO: Как организовать создание пользователя? Типа в FastAPI делаем болванку датакласса, затем передаём в repo user
        pass

    def getUser(user_id: int)->UserDTO:
        try:
            user = self.repo.get_user(user_id)
            return user
        except NotFoundError as e:
            raise UserNotFoundError(user_id)
        except:
            #TODO: Необработанное исключение

    #TODO: Как проверять имеет ли право пользователь менять user_id
    def updateUser(account_id: int, user_id: int, command: UserCommand)->UserDTO:
        if not self.auth_service.canUpdateUser(account_id, user_id):
            raise ForbiddenError(account_id, "updateUser", {"user_id": user_id})
        try:
            user = self.repo.get_user(user_id) #TODO: Optional[User]
            user.apply(command)
            self.repo.update_user(user)
            return user
        except NotFoundError as e:
            raise UserNotFoundError(user_id)
        except NotUpdatedError as e:
            raise UserUpdateError(user_id)
        except:
            raise UnknownServiceException("updateUser")

    def deleteUser(account_id: int, user_id: int):
        if not self.auth_service.canDeleteUser(account_id, user_id):
            raise ForbiddenError(account_id, "delete_user", {"user_id": user_id})
        try:
            self.repo.delete_user(user_id)
        except NotFoundError as e:
            raise UserNotFoundError(user_id)
        except NotDeletedError as e:
            raise UserDeleteError(user_id)
        except:
            #TODO: Необработанное исключение

    def getUsersShort(account_id: int, search_params: UserSearchParams)->List[UserShort]:
        try:
            users: List[UserShort] = self.repo.select_users_short(search_params)
            return users
        except:
            #TODO: Необработанное исключение