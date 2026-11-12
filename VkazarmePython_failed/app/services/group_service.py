from typing import List

from ..dto import GroupDTO, GroupShort
from ..repositories import GroupRepository
from .auth_service import AuthService
from .exceptions import *

class GroupService:
    def __init__(self, repo: GroupRepository, auth_service: AuthService):
        self.repo = repo
        self.auth_service = auth_service

    def addGroup(self, account_id: int, group: GroupDTO)->GroupDTO:
        if not self.auth_service.canCreateGroup(account_id):
            raise ForbiddenError(account_id, "addGroup", {})
        try:
            group = self.repo.addGroup(group)
            return group
        except:
            raise ResourceNotCreatedError()
            #raise UnknownServiceException("addGroup")
    
    def updateGroup(self, account_id: int, group_id: int, command: GroupUpdateCommand)->GroupDTO:
        if not self.auth_service.canCreateGroup(account_id):
            raise ForbiddenError(account_id, "updateGroup", {})
        try:
            group = self.repo.getGroup(group_id)
            group.apply(command)
            self.repo.updateGroup(group)
            return group
        except NotFoundError as e:
            raise ResourceNotFoundError()
        except NotUpdatedError as e:
            raise ResourceNotUpdatedError()
        except:
            raise UnknownServiceException("updateGroup")

    def deleteGroup(self, account_id: int, group_id: int):
        if not self.auth_service.canDeleteGroup(account_id, group_id):
            raise ForbiddenError(account_id, "deleteGroup", {"group_id": group_id})
        try:
            self.repo.deleteGroup(group_id)
        except NotFoundError as e:
            raise ResourceNotFoundError()
        except NotDeletedError as e:
            raise ResourceNotDeletedError()
        except:
            raise UnknownServiceException("deleteGroup")