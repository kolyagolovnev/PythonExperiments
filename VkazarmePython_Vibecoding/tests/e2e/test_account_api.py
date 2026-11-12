"""End-to-end tests for /account: the spec's happy path and error codes."""

from httpx import AsyncClient

from tests.conftest import ADMIN_EMAIL, sign_up_and_sign_in


class TestSignup:

    async def test_signup_returns_200(self, client: AsyncClient):
        response = await client.post("/account/signup",
                                     json={"email": "user1@t.com", "password": "Password123"})
        assert response.status_code == 200

    async def test_signup_duplicate_email_is_400(self, client: AsyncClient):
        await sign_up_and_sign_in(client, "user1@t.com")
        response = await client.post("/account/signup",
                                     json={"email": "user1@t.com", "password": "Password123"})
        assert response.status_code == 400

    async def test_signup_malformed_email_is_400(self, client: AsyncClient):
        response = await client.post("/account/signup",
                                     json={"email": "not-an-email", "password": "Password123"})
        assert response.status_code == 400

    async def test_signup_short_password_is_400(self, client: AsyncClient):
        # minLength 6 from the spec, enforced by the DTO
        response = await client.post("/account/signup",
                                     json={"email": "user1@t.com", "password": "123"})
        assert response.status_code == 400

    async def test_signup_missing_field_is_400(self, client: AsyncClient):
        # RequestValidationError is mapped to 400 per the spec (not FastAPI's 422)
        response = await client.post("/account/signup", json={"email": "user1@t.com"})
        assert response.status_code == 400


class TestSignin:

    async def test_signin_returns_jwt_string(self, client: AsyncClient):
        await sign_up_and_sign_in(client, "user1@t.com")
        response = await client.post("/account/signin",
                                     json={"email": "user1@t.com", "password": "Password123"})
        assert response.status_code == 200
        token = response.json()
        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # header.payload.signature

    async def test_signin_wrong_password_is_403(self, client: AsyncClient):
        await sign_up_and_sign_in(client, "user1@t.com")
        response = await client.post("/account/signin",
                                     json={"email": "user1@t.com", "password": "Nope123"})
        assert response.status_code == 403

    async def test_signin_unknown_email_is_403(self, client: AsyncClient):
        response = await client.post("/account/signin",
                                     json={"email": "ghost@t.com", "password": "Password123"})
        assert response.status_code == 403

    async def test_admin_can_sign_in(self, client: AsyncClient):
        await sign_up_and_sign_in(client, ADMIN_EMAIL)
        response = await client.post("/account/signin",
                                     json={"email": ADMIN_EMAIL, "password": "Password123"})
        assert response.status_code == 200
