from domains import *
from repositories import *

class AuthService:
    def __init__(self, repo: AuthRepository):
        self.repo = repo
        
    def canDeleteUser(account_id: int, user_id: int)->bool:
        if account_id == user_id:
            return True
        
        #TODO: Проверка на наличие прав администратора
        return False

    def canUpdateUser(account_id: int, user_id: int)->bool:
        if account_id == user_id:
            return True
        return False
    
    def canCreateGroup(account_id: int)->bool:
        #TODO: Проверка, что account_id == admin_id
        return False

    def canUpdateGroup(account_id: int, group_id: int)->bool:
        #TODO: Проверка, либо account_id == admin_id, 
        #TODO: либо account_id имеет какие-то права на изменение группы (Но в UseCase я опустил этот вопрос, так что скорее всего только админ может изменять описание группы)
        return False

    def canDeleteGroup(account_id: int, group_id: int)->bool:
        #TODO: Проверка, что account_id == admin_id
        return False

    def canAddPaste(account_id: int, group_id: int)->bool:
        #TODO: Проверка, может ли account опубликовывать ПОСТЫ в группе
        return False

    def canDeletePaste(account_id: int, paste_id: int)->bool:
        #TODO:
        return False
    # TODO: другие методы для проверки возможностей пользователя