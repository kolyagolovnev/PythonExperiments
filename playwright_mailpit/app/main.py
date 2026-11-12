import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Хранилища в памяти (in-memory)
unconfirmed_accounts: dict[str, dict] = {}   # id -> {email, password, key}
confirmed_accounts: dict[str, str] = {}       # email -> password

# Параметры SMTP (Mailpit) и внутренний домен Docker
SMTP_HOST = "mailpit"
SMTP_PORT = 1025
APP_DOMAIN = "http://app:8000"                 # домен внутри Docker-сети
SENDER_EMAIL = "noreply@example.com"


class SignupRequest(BaseModel):
    email: str
    password: str


class SigninRequest(BaseModel):
    email: str
    password: str


def send_email(to_email: str, subject: str, text_body: str, html_body: str):
    """Отправляет письмо через SMTP-сервер Mailpit."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.send_message(msg)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/account/signup")
def signup(req: SignupRequest):
    account_id = str(uuid.uuid4())
    key = str(uuid.uuid4())

    unconfirmed_accounts[account_id] = {
        "email": req.email,
        "password": req.password,
        "key": key,
    }

    confirmation_url = (
        f"{APP_DOMAIN}/account/signup/confirmation"
        f"?id={account_id}&key={key}"
    )

    send_email(
        to_email=req.email,
        subject="Подтверждение аккаунта",
        text_body=(
            "Для подтверждения аккаунта перейдите по ссылке:\n\n"
            f"{confirmation_url}"
        ),
        html_body=(
            "<p>Для подтверждения аккаунта перейдите по ссылке:</p>"
            f'<p><a href="{confirmation_url}">{confirmation_url}</a></p>'
        ),
    )

    return {"message": "Письмо с подтверждением отправлено", "account_id": account_id}


@app.get("/account/signup/confirmation")
def confirm_signup(id: str, key: str):
    account = unconfirmed_accounts.get(id)
    if not account:
        raise HTTPException(status_code=404, detail="Аккаунт не найден")
    if account["key"] != key:
        raise HTTPException(status_code=403, detail="Неверный ключ подтверждения")

    # Перенос в подтверждённые
    confirmed_accounts[account["email"]] = account["password"]
    del unconfirmed_accounts[id]

    return {"message": "Аккаунт успешно подтверждён"}


@app.post("/account/signin")
def signin(req: SigninRequest):
    # Подтверждённый аккаунт
    if req.email in confirmed_accounts:
        if confirmed_accounts[req.email] == req.password:
            return {"message": "Успешный вход"}
        raise HTTPException(status_code=401, detail="Неверный пароль")

    # Неподтверждённый аккаунт
    for acc in unconfirmed_accounts.values():
        if acc["email"] == req.email:
            raise HTTPException(status_code=403, detail="Аккаунт не подтверждён")

    # Не существует
    raise HTTPException(status_code=404, detail="Аккаунт не найден")

