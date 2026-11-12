from pydantic_settings import BaseSettings, SettingsConfigDict
from bcrypt import gensalt

class Settings(BaseSettings):
    DOMAIN: str = "mydomain.com"
    DATABASE_URL: str = "TODO: Надо вставить URL из Docker Compose"
    APP_NAME: str = "MyFastAPIApp"
    DEBUG: bool = False
    SECRET: str = "change_this_to_a_strong_random_secret"
    ALGORITHM: str = "HS256"
    PASSWORD_HASH_SALT: str = gensalt().decode()
    GOOGLE_RESOURSE_URI: str = "https://oauth2.googleapis.com/token"
    VK_RESOURCE_URI: str = "https://oauth.vk.com/access_token"
    OAUTH_STATE_BYTELEN: int = 32
    EMAIL_CONFIRM_KEY_BYTELEN: int = 64
    TEMP_ACCOUNT_TTL_IN_SECONDS: int = 3600
    SERVER_ADDRESS: str = "localhost"
    SERVER_PORT: int = 10000
    EMAIL_ADDRESS: str = "myemail@company.com"
    EMAIL_PASSWORD: str = "password"
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
