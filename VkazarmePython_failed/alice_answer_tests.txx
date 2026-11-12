Ниже — готовые E2E‑тесты на `pytest` + `httpx` для FastAPI, покрывающие основные сценарии по твоим endpoint’ам. Тесты написаны в стиле, близком к BDD: понятные имена, чёткие Given‑When‑Then‑шаги внутри кода, фикстуры для состояния и изолированные сценарии.

## Подготовка

```bash
pip install pytest httpx
```

Предполагаем, что твой FastAPI-сервер запускается на `http://localhost:8000` (или подставляй свой URL).

---

## tests/conftest.py

```python
import pytest
import httpx
from typing import Dict, Any

BASE_URL = "http://localhost:8000/api/v1"

@pytest.fixture(scope="session")
def client():
    return httpx.Client(base_url=BASE_URL, follow_redirects=True)

@pytest.fixture
def user_credentials() -> Dict[str, Any]:
    return {
        "email": "test_user@example.com",
        "password": "StrongPass123",
    }

@pytest.fixture
def admin_credentials() -> Dict[str, Any]:
    # В реальном проекте это отдельный пользователь с ролью admin
    return {
        "email": "admin@example.com",
        "password": "AdminPass123",
    }

@pytest.fixture
def auth_token(client, user_credentials):
    resp = client.post("/account/signin", json=user_credentials)
    assert resp.status_code in (200, 201), f"Signin failed: {resp.text}"
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    assert token, "No token returned"
    return token

@pytest.fixture
def admin_auth_token(client, admin_credentials):
    resp = client.post("/account/admin", json=admin_credentials)
    assert resp.status_code == 200, f"Admin signin failed: {resp.text}"
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    assert token, "No admin token returned"
    return token

@pytest.fixture
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}

@pytest.fixture
def admin_headers(admin_auth_token):
    return {"Authorization": f"Bearer {admin_auth_token}"}
```

---

## tests/test_account.py

```python
import httpx

def test_signup_and_signin(client, user_credentials):
    # Given: новый пользователь
    # When: регистрируется
    resp_signup = client.post("/account/signup", json=user_credentials)
    assert resp_signup.status_code in (200, 201)

    # Then: может войти
    resp_signin = client.post("/account/signin", json=user_credentials)
    assert resp_signin.status_code == 200
    data = resp_signin.json()
    assert "token" in data or "access_token" in data

def test_signin_invalid_credentials(client, user_credentials):
    # Given: неверные данные
    bad_creds = {**user_credentials, "password": "wrong"}
    # When: пытается войти
    resp = client.post("/account/signin", json=bad_creds)
    # Then: ошибка 401
    assert resp.status_code == 401

def test_admin_login(client, admin_credentials):
    # Given: админские данные
    # When: входит в админ-панель
    resp = client.post("/account/admin", json=admin_credentials)
    # Then: успех
    assert resp.status_code == 200
```

---

## tests/test_users.py

```python
def test_get_users_list(client, headers):
    # Given: авторизованный пользователь
    # When: запрашивает список пользователей
    resp = client.get("/users", headers=headers)
    # Then: успешный ответ
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

def test_get_user_profile(client, headers, auth_token):
    # Given: авторизованный пользователь, знаем свой ID (упрощённо: берём из токена или заранее создаём)
    # Для примера: сначала получим список и возьмём первого пользователя
    resp_list = client.get("/users", headers=headers, params={"limit": 1})
    assert resp_list.status_code == 200
    users = resp_list.json()
    if not users:
        pytest.skip("No users found to test profile")
    user_id = users[0]["id"]

    # When: запрашиваем профиль
    resp = client.get(f"/users/{user_id}", headers=headers)
    # Then: успех и корректная структура
    assert resp.status_code == 200
    profile = resp.json()
    assert profile["id"] == user_id

def test_update_profile(client, headers, auth_token):
    # Given: авторизованный пользователь
    # Сначала узнаём свой ID (в реальном проекте он приходит в ответе на /account/me или хранится в токене)
    resp_list = client.get("/users", headers=headers, params={"limit": 1})
    users = resp_list.json()
    if not users:
        pytest.skip("No users to update")
    user_id = users[0]["id"]

    patch_data = {"job": "Новый замполит", "rang": 6}
    # When: обновляет профиль
    resp = client.patch(f"/users/{user_id}", json=patch_data, headers=headers)
    # Then: успех
    assert resp.status_code == 200

def test_delete_user_by_admin(client, admin_headers, admin_auth_token):
    # Given: админ авторизован, есть тестовый пользователь (для простоты создадим нового)
    new_user = {
        "email": "temp_user_for_delete@example.com",
        "password": "TempPass123"
    }
    resp_signup = client.post("/account/signup", json=new_user)
    assert resp_signup.status_code in (200, 201)
    # Получим ID нового пользователя (в реальности лучше хранить ID после регистрации)
    resp_list = client.get("/users", headers=admin_headers, params={"name": "temp"})
    users = resp_list.json()
    target_id = None
    for u in users:
        if u.get("email") == new_user["email"]:
            target_id = u["id"]
            break
    if not target_id:
        pytest.skip("Could not find newly created user for delete test")

    # When: админ удаляет пользователя
    resp = client.delete(f"/users/{target_id}", headers=admin_headers)
    # Then: удаление успешно
    assert resp.status_code == 204
```

---

## tests/test_friends.py

```python
def test_add_and_remove_friend(client, headers, auth_token):
    # Given: два пользователя (для теста используем существующих, иначе создаём)
    resp_users = client.get("/users", headers=headers, params={"limit": 2})
    assert resp_users.status_code == 200
    users = resp_users.json()
    if len(users) < 2:
        pytest.skip("Not enough users for friend test")
    me = users[0]
    friend = users[1]

    # When: добавляем друга
    resp_add = client.post(
        f"/users/{me['id']}/friends",
        json={"friend_id": friend["id"]},  # адаптируй под схему Friend
        headers=headers
    )
    assert resp_add.status_code in (200, 201)

    # Then: друг есть в списке
    resp_friends = client.get(f"/users/{me['id']}/friends", headers=headers)
    assert resp_friends.status_code == 200
    friends_list = resp_friends.json()
    friend_ids = [f["id"] for f in friends_list]
    assert friend["id"] in friend_ids

    # When: удаляем друга
    resp_del = client.delete(
        f"/users/{me['id']}/friends/{friend['id']}",
        headers=headers
    )
    assert resp_del.status_code == 204

    # Then: друга нет в списке
    resp_friends_after = client.get(f"/users/{me['id']}/friends", headers=headers)
    friends_after = resp_friends_after.json()
    friend_ids_after = [f["id"] for f in friends_after]
    assert friend["id"] not in friend_ids_after
```

---

## tests/test_groups.py

```python
def test_create_group_by_admin(client, admin_headers):
    # Given: админ авторизован
    group_data = {
        "name": "209-я бригада (тест)",
        "description": "Тестовая группа сослуживцев",
        "photo_url": "https://example.com/photo.jpg"
    }
    # When: создаёт группу
    resp = client.post("/groups", json=group_data, headers=admin_headers)
    # Then: группа создана
    assert resp.status_code == 201
    group = resp.json()
    assert group["name"] == group_data["name"]
    group_id = group["id"]

    # Cleanup: удаляем группу после теста
    client.delete(f"/groups/{group_id}", headers=admin_headers)

def test_subscribe_and_unsubscribe(client, headers, auth_token):
    # Given: пользователь авторизован, есть группа
    resp_groups = client.get("/groups", headers=headers, params={"limit": 1})
    groups = resp_groups.json()
    if not groups:
        pytest.skip("No groups to subscribe to")
    group = groups[0]

    # When: подписывается на группу
    sub_data = {"group_id": group["id"], "sub_type": "group"}
    resp_sub = client.post(f"/users/{group['id'] if False else 1}/subscriptions",  # здесь нужен реальный UserID
                           json=sub_data,
                           headers=headers)
    # Примечание: в реальном тесте подставь корректный UserID (например, из фикстуры)
    # Для демонстрации оставим заглушку — в проекте замени на реальный ID
    # assert resp_sub.status_code in (200, 201)

    # Аналогично — отписку реализуй по аналогии с удалением друзей
```

> ⚠️ В тестах выше есть места, где нужно подставить реальные ID пользователей (например, в подписках). В полноценном BDD/TDD-подходе такие ID либо возвращаются при создании сущностей и переиспользуются в рамках сценария, либо хранятся в фикстурах.

---

## tests/test_pastes_and_comments.py

```python
def test_post_and_comment(client, headers, auth_token):
    # Given: есть группа и пользователь авторизован
    resp_groups = client.get("/groups", headers=headers, params={"limit": 1})
    groups = resp_groups.json()
    if not groups:
        pytest.skip("No groups for paste test")
    group = groups[0]

    paste_data = {
        "title": "Пост для теста",
        "content": "Текст поста",
        "group_id": group["id"]
    }
    # When: пользователь публикует пост
    resp_paste = client.post(f"/groups/{group['id']}/pastes", json=paste_data, headers=headers)
    assert resp_paste.status_code in (200, 201)
    paste = resp_paste.json()
    paste_id = paste["id"]

    # When: оставляет комментарий
    comment_data = {
        "content": "Отличный пост!",
        "paste_id": paste_id
    }
    resp_comment = client.post(
        f"/groups/{group['id']}/pastes/{paste_id}/comments",
        json=comment_data,
        headers=headers
    )
    assert resp_comment.status_code in (200, 201)

    # Then: комментарий есть
    resp_comments = client.get(
        f"/groups/{group['id']}/pastes/{paste_id}/comments",
        headers=headers
    )
    assert resp_comments.status_code == 200
    comments = resp_comments.json()
    assert len(comments) >= 1
```

---

## tests/test_chats.py

```python
def test_chat_lifecycle(client, headers, auth_token):
    # Given: два пользователя
    resp_users = client.get("/users", headers=headers, params={"limit": 2})
    users = resp_users.json()
    if len(users) < 2:
        pytest.skip("Not enough users for chat test")
    u1, u2 = users[0], users[1]

    # When: создаём чат между ними
    chat_data = {"participants": [u1["id"], u2["id"]]}
    resp_create = client.post("/chats", json=chat_data, headers=headers)
    assert resp_create.status_code in (200, 201)
    chat = resp_create.json()
    chat_id = chat["id"]

    # Then: чат существует
    resp_get = client.get(f"/chats/{chat_id}", headers=headers)
    assert resp_get.status_code == 200

    # When: отправляем сообщение
    msg_data = {"content": "Привет, сослуживец!", "sender_id": u1["id"]}
    resp_msg = client.post(f"/chats/{chat_id}/messages", json=msg_data, headers=headers)
    assert resp_msg.status_code in (200, 201)

    # Then: сообщение видно
    resp_msgs = client.get(f"/chats/{chat_id}/messages", headers=headers)
    assert resp_msgs.status_code == 200
    msgs = resp_msgs.json()
    assert len(msgs) >= 1
```

---

## tests/test_media.py

```python
import io

def test_upload_media(client, headers):
    # Given: файл для загрузки
    file_content = b"fake image content"
    files = {"file": ("avatar.jpg", file_content, "image/jpeg")}

    # When: загружаем медиа
    resp = client.post("/media", files=files, headers=headers)
    # Then: загрузка успешна
    assert resp.status_code in (200, 201)
```

---

## Как это соотносится с BDD/TDD

- **TDD**: каждый тест можно запускать до реализации эндпоинта — он будет падать («красный»), затем ты реализуешь логику, чтобы тест прошёл («зелёный»), затем рефакторишь.
- **BDD**: имена тестов и структура (Given/When/Then в комментариях) делают тесты понятными для бизнеса; при необходимости их можно обернуть в Gherkin (Behave/Faker) без изменения логики вызовов.

## Рекомендации по улучшению

1. **Изоляция данных**: для каждого теста создавай уникальные email/названия (например, с UUID), чтобы тесты не конфликтовали.
2. **Фикстуры-сценарии**: выноси создание пользователей/групп в отдельные фикстуры, возвращающие ID сущностей.
3. **Очистка**: после каждого теста удаляй созданные сущности (или используй транзакционную БД с отменой изменений).
4. **Роли**: отдельно тестируй сценарии «обычный пользователь vs админ» на тех эндпоинтах, где есть проверка прав.
5. **Негативные сценарии**: добавь тесты на 403, 404, 422 и т.д. (например, попытка удалить чужого друга или несуществующую группу).

Если скажешь, какой именно стек базы данных и как у тебя устроены фикстуры (например, SQLAlchemy + pytest-asyncio), я адаптирую тесты под полноценную интеграцию с БД и транзакциями.
