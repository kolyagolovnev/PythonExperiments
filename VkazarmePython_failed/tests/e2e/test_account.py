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
