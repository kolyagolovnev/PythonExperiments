from repositories import SignRepository, SignCacheRepository
from domains.models import *
from .exceptions import *
from settings import Settings
from dataclasses import dataclass
import dns.resolver
import bcrypt
import secrets
import smtplib
from urllib.parse import quote
from email.message import EmailMessage
#TODO: Добавить Redis

#TODO: Надо получить адрес smtp-сервера и порт

@dataclass
class SMTP_DATA:
    server: str
    port: int

class MailSubService:
    def __init__(self, settings: Settings):
        self.settings = settings

    def validateEmailAndGetSmtp(self, email_address: str)->SMTP_DATA:
        # 1. Валидация базового формата (наличие @)
        if "@" not in email_address or email_address.count("@") > 1:
            raise InvalidEmail("invalid structure of email address")

        domain = email_address.split("@")[-1].lower().strip()
    
        # Список стоп-слов для блокировки серверов временной почты
        # Сервисы меняют домены каждый день, но их MX-серверы всегда содержат эти маркеры
        #TODO: Надо брать из файла или другого источника все возможные слова, потому что эти данные не фиксированные, но это учебный проект, так что пока пофигу
        BLACKLIST_KEYWORDS = [
            "temp", "disposable", "dropmail", "trash", "10min", 
            "anon", "fake", "mailinator", "yopmail", "getairmail"
        ]
        try:
            # 2. Запрашиваем MX (Mail Exchange) записи домена из DNS
            answers: dns.resolver.Answer = dns.resolver.resolve(domain, 'MX')
        
            # Сортируем записи по приоритету (preference) — чем меньше число, тем важнее сервер
            sorted_answers = sorted(answers, key=lambda r: r.preference)
        
            # Берем самый приоритетный MX-сервер и очищаем его от финальной точки
            main_mx_server = sorted_answers[0].exchange.to_text().lower().rstrip('.')
        
            # 3. Защита: проверяем имя MX-сервера на наличие стоп-слов
            if any(keyword in main_mx_server for keyword in BLACKLIST_KEYWORDS):
                raise InvalidEmail("temporary email service")
            
            # 4. Определение SMTP настроек на основе анализа MX-сервера
            # (Помогает правильно настроить отправку для корпоративных доменов на базе Яндекса/Google)
            if "google" in main_mx_server:
                return SMTP_DATA(server="://gmail.com", port=465)
            elif "yandex" in main_mx_server:
                return SMTP_DATA(server="smtp.yandex.ru", port=465)
            elif "mail.ru" in main_mx_server or "vmail.ru" in main_mx_server:
                return SMTP_DATA(server="smtp.mail.ru", port=465)
            elif "outlook" in main_mx_server or "protection.outlook" in main_mx_server:
                return SMTP_DATA(server="://office365.com", port=587)
            
            # 5. Если это независимый собственный корпоративный сервер компании
            return SMTP_DATA(server=main_mx_server, port=587)
        
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            raise InvalidEmail("mail domain not exists")
        except Exception as e:
            raise InvalidEmail(f"dns error ({str(e)})")
    
    def sendEmail(self, email: str, head: str, content: str, smtp_info: SMTP_DATA):
        mail_msg = EmailMessage();
        mail_msg["From"] = self.settings.EMAIL_ADDRESS
        mail_msg["To"] = email
        mail_msg["Subject"] = head
        mail_msg.set_content(content)

        try:
            with smtplib.SMTP(smtp_info.server, smtp_info.port, timeout=10) as server:
                server.starttls()
                server.login(self.settings.EMAIL_ADDRESS, self.settings.EMAIL_PASSWORD)
                server.send_message(mail_msg)
        except:
            raise MailSenderException("Mail sending problem")

class SignService:
    def __init__(self, repo: SignRepository, cache_repo: SignCacheRepository, mail_service: MailSubService, settings: Settings):
        self.mail_service = mail_service
        self.repo = repo
        self.cache_repo = cache_repo
        self.settings = settings

    def signInInit(self)->SignInInit:
        state_bytes = secrets.token_bytes(self.settings.OAUTH_STATE_BYTELEN)
        state = state_bytes.hex()
        return SignInInit(state=state)

    #TODO: Нужно проверить email на корректность
    #TODO: Надо изменить repo, чтобы не было методов по типу checkUserEmailExistence, а только для чтения и записи

    async def signUp(self, data: SignUpData):
        if self.repo.checkUserEmailExistence(data.email):
            raise EmailIsBusy()
        smtp_data: SMTP_DATA = self.mail_service.validateEmailAndGetSmtp(data.email)
        try:
            key = secrets.token_bytes(self.settings.EMAIL_CONFIRM_KEY_BYTELEN).hex()
            hashed_password: bytes = bcrypt.hashpw(data.password.encode(), self.settings.PASSWORD_HASH_SALT.encode())
            await self.cache_repo.addTempAccount(TempAccountData(email=data.email, hashed_password=hashed_password, key=key, oauth_provider=Provider.SELF, oauth_id=""))
            link: str = f"https://{self.settings.DOMAIN}/signup/confirm?email={quote(data.email)}&key={key}"
            content: str = f"""
            <h3>Подтверждение аккаунта</h3>
            <p>Для завершения регистрации перейдите по ссылке:</p>
            <a href="{link}">{link}</a>
            """
            #TODO: Нужно не ждать, пока почта отправится
            self.mail_service.sendEmail(data.email, head="Подтверждение аккаунта", content=content, smtp_info=smtp_data)
        except:
            #TODO: logger
            print("Cannot insert sign")

    async def signUpConfirm(self, email: str, key: str):
        try:
            tmp_account = await self.cache_repo.getTempAccount(email=email)
        except:
            raise SignUpCannotGetTempAccount()
        if tmp_account.key != key:
            raise SignUpInvalidKey()
        try:
            await self.repo.insertAccount(tmp_account)
        except:
            raise SignUpAccountConfirmedButNotCreated()
    """
    def signInExternalProvider(self, provider: Provider, data: OAuthCallback)->AuthToken:
        if provider == Provider.VK:
            #TODO: Нужно сделать запрос на VK с введеными ключами ()
            pass
        elif provider == Provider.GOOGLE:
            #TODO: Нужно сделать запрос на GOOGLE с введенными ключами
            pass
        else:
            raise SignUpProviderNotSupported(str(request.provider))
    """

    async def signInExternalProvider(self, provider: Provider, data: OAuthCallback)->AuthToken:
        pass #TODO: Нужно создать OAuth2-авторизацию - сделаем это в самый последний момент


    async def signInUsual(self, request: SignRequest)->AuthToken:
        try:
            request.password = bcrypt.hashpw(request.password.encode(), self.settings.PASSWORD_HASH_SALT.encode()).decode()
            data: AuthToken = await self.repo.findAccount(request)
            return data
        except:
            raise IncorrectEmailOrPassword()

    def signInAdmin(self, request: SignRequest)->AuthToken:
        #TODO: Нужно вход осуществлять с запросом из Redis
        pass