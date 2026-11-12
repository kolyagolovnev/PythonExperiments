from ..repositories import PasteRepository
from .auth_service import AuthService
from ..dto import *

class PasteService:
    def __init__(self, repo: PasteRepository, auth_service: AuthService):
        self.repo = repo
        self.auth_service = auth_service

    def addPaste(self, account_id: int, paste: PasteDTO)->PasteDTO:
        #TODO:
        pass

    def deletePaste(self, account_id: int, paste_id: int):
        if not auth_service.canDeletePaste(account_id, paste_id):
                    