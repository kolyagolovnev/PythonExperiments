from .base import SignRepository
from domains.models import *
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey,
    Integer, String, Text, UniqueConstraint, func, select, Enum as SQLEnum
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

"""
	id BIGSERIAL PRIMARY KEY,
	name TEXT NOT NULL,
	surname TEXT NOT NULL,
	email VARCHAR(200),--TODO: валидация Email
    password_hash VARCHAR(50),
    oauth_provider PROVIDER_ENUM,
    oauth_user_id TEXT,
	rang INT NOT NULL,
	job TEXT NOT NULL,
	status TEXT NOT NULL,
	subdivision TEXT NOT NULL,
	photo_url TEXT NOT NULL,
"""

class PostgresBase(DeclarativeBase):
    pass

class Account(PostgresBase):
    __tablename__ = "accounts"    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Ссылка на существующий тип в БД. 
    # name должен совпадать с именем типа в PostgreSQL (регистр важен!)
    provider: Mapped[str] = mapped_column(SQLEnum("vk", "google", "self", name="provider_enum", create_type=False))
    
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)

    __table_args__ = (
        # Уникальность пары: провайдер + ID пользователя
        {"postgresql_exclude": None}, # Просто заглушка, чтобы __table_args__ работал корректно
        # Реальное ограничение ниже:
        # В SQLAlchemy UniqueConstraint работает независимо от exclude
    )
    
    # Добавляем ограничение явно
    __table_args__ = (
        UniqueConstraint('provider', 'external_id', name='uq_accounts_provider_external'),
    )


class SQLAlchemySignRepository(SignRepository):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def checkUserEmailExistence(self, email: str)->bool:
        return True #TODO

    async def insertAccount(self, account: AccountData):
        pass #TODO

    async def findAccount(self, sign: SignRequest)->AuthToken:
        return AuthToken(sub="something", exp=1111111) #TODO
