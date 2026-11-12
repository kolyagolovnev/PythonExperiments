from base import AuthRepository
from sqlalchemy.ext.asyncio import AsyncSession

class SQLAlchemyRepository(AuthRepository):
    def __init__(self, db: AsyncSession):
        self.db = db
    
    #TODO: Нужно придумать методы