import pytest

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
