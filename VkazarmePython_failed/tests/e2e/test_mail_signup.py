import re
import time
import requests
import pytest
import os
from playwright.sync_api import sync_playwright

APP_URL = "http://app:8000"
MAILPIT_API = "http://mailpit:8025"

# Регэкс для извлечения URL подтверждения из тела письма
URL_REGEX = re.compile(
    r"https?://[^\s\"'<>]+/account/signup/confirmation\?id=[^&\s\"'<>]+&key=[^\s\"'<>]+"
)


def wait_for_app(timeout: int = 30):
    """Ждёт, пока FastAPI-приложение не начнёт отвечать."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{APP_URL}/health", timeout=2)
            if r.status_code == 200:
                return
        except requests.ConnectionError:
            pass
        time.sleep(1)
    raise RuntimeError("Приложение не ответило за отведённое время")


def get_confirmation_url_from_mailpit(timeout: int = 15) -> str:
    """Получает последнее письмо из Mailpit и извлекает URL подтверждения."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(f"{MAILPIT_API}/api/v1/messages")
        data = resp.json()
        messages = data.get("messages", [])

        if messages:
            # Берём последнее (новейшее) письмо
            msg_id = messages[0]["ID"]
            detail = requests.get(f"{MAILPIT_API}/api/v1/message/{msg_id}")
            detail_json = detail.json()

            # Mailpit возвращает поля HTML и Text
            body = detail_json.get("Text") or detail_json.get("HTML") or ""
            match = URL_REGEX.search(body)
            if match:
                return match.group(0)

        time.sleep(1)

    raise RuntimeError("Письмо с подтверждением не найдено в Mailpit")


def test_full_signup_confirmation_signin_flow():
    email = "testuser@example.com"
    password = "SuperSecret123!"

    # 1. Ждём готовности приложения
    wait_for_app()

    # 2. Очищаем ящик Mailpit перед тестом
    requests.delete(f"{MAILPIT_API}/api/v1/messages")

    # 3. Регистрируемся — /account/signup
    resp = requests.post(
        f"{APP_URL}/account/signup",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, f"Signup failed: {resp.text}"

    # 4. Вход до подтверждения — ожидаем 403
    resp = requests.post(
        f"{APP_URL}/account/signin",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 403, (
        f"Expected 403 for unconfirmed account, got {resp.status_code}"
    )



    # 5. Получаем URL подтверждения из Mailpit
    confirmation_url = get_confirmation_url_from_mailpit()
    assert "id=" in confirmation_url and "key=" in confirmation_url

    # 6. Подтверждаем аккаунт через requests (вместо Playwright)
    resp = requests.get(confirmation_url, timeout=10)
    assert resp.status_code == 200, f"Подтверждение вернуло {resp.status_code}: {resp.text}"
    assert "подтвержд" in resp.text.lower(), f"Неверный ответ: {resp.text}"

    # 7. Вход после подтверждения — ожидаем 200
    resp = requests.post(
        f"{APP_URL}/account/signin",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, (
        f"Expected 200 after confirmation, got {resp.status_code}: {resp.text}"
    )

    # 8. Вход с несуществующим аккаунтом — ожидаем 404
    resp = requests.post(
        f"{APP_URL}/account/signin",
        json={"email": "ghost@example.com", "password": "nope"},
    )
    assert resp.status_code == 404, (
        f"Expected 404 for non-existent account, got {resp.status_code}"
    )

