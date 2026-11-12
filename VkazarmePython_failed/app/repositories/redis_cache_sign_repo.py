import redis.asyncio as redis
import json

from .cache_repo import SignCacheRepository
from .exceptions import *
from domains.models import *
from settings import Settings

class RedisCacheSignRepository(SignCacheRepository):
    def __init__(self, client: redis.Redis, settings: Settings):
        self.client = client
        self.settings = settings

    async def getTempAccount(self, email: str) -> TempAccountData:
        try:
            json_object = await self.client.get(f"accounts:{email}")
        except:
            raise ConnectionError
        if json_object is None:
            raise NotFoundError
        return TempAccountData(email=email, **json.loads(json_object))

    async def addTempAccount(self, account_data: TempAccountData):
        data_dict = account_data.__dict__
        data_dict.pop('email')
        key = f"accounts:{account_data.email}"
        try:
            await self.client.set(key, json.dumps(data_dict), ex=self.settings.TEMP_ACCOUNT_TTL_IN_SECONDS)
        except:
            raise ConnectionError
    