"""E2E coverage for the frontend/CORS middleware (app/middleware.py).

The middleware is registered by ``create_app`` and does not add any routes to
the OpenAPI schema: it serves the bundled client at ``/`` and decorates every
HTTP response with CORS headers.
"""

from httpx import AsyncClient


class TestFrontendAtRoot:

    async def test_root_serves_the_client(self, client: AsyncClient):
        response = await client.get("/")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "<title>ПЛАЦ" in response.text

    async def test_index_html_is_also_served(self, client: AsyncClient):
        response = await client.get("/index.html")
        assert response.status_code == 200
        assert response.text == (await client.get("/")).text

    async def test_head_has_no_body(self, client: AsyncClient):
        response = await client.head("/")
        assert response.status_code == 200
        assert response.content == b""

    async def test_api_namespace_is_not_shadowed(self, client: AsyncClient):
        response = await client.get("/users")
        assert response.status_code == 401  # API route, not static content
        assert "text/html" not in response.headers.get("content-type", "")


class TestCors:

    async def test_preflight_is_answered_without_hitting_the_api(self, client: AsyncClient):
        response = await client.options(
            "/users/1",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "*"
        assert "PATCH" in response.headers["access-control-allow-methods"]
        assert "authorization" in response.headers["access-control-allow-headers"].lower()

    async def test_actual_response_has_cors_headers(self, client: AsyncClient):
        response = await client.get("/", headers={"Origin": "http://localhost:5173"})
        assert response.headers["access-control-allow-origin"] == "*"
        assert "Origin" in response.headers["vary"]

    async def test_error_response_has_cors_headers(self, client: AsyncClient):
        response = await client.get("/users", headers={"Origin": "http://localhost:5173"})
        assert response.status_code == 401
        assert response.headers["access-control-allow-origin"] == "*"
