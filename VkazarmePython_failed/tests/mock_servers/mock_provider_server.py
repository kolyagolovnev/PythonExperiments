from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import RedirectResponse, JSONResponse, Response
import time
import random
import urllib.parse

"""
Как происходит авторизация/регистрация через Google/VK
0)Мы заранее у сервера Google/VK регистрируем наше приложение
1)Пользователь делает в браузере redirect, например, на https://accounts.google.com/o/oauth2/v2/auth c данными
{
    client_id: "id of my web app in Google/VK Databases",
    redirect_uri: "https://myweb/authorize", - один из адресов в белом списке на Google/VK базах данных, куда мы перенаправляем запрос для получения токенов на бэкенде
    response_type: "code", - в моём случае всегда имеет значение "code" - режим Authorization Flow Code
    scope: "openid%20email%20profile", - список прав, на которые мы запрашиваем разрешения
    state: "случайная строка", - нужна для защиты от CSRF атак, хз когда проверяется
    access_type: "online", - если нужен refresh token, то online, иначе offline, но нам по сути нужно только 1 раз получить идентификатор пользователя + какие-то его данные для заполнения
    prompt: "consent" - это что-то связанное с экраном согласия (всегда его показывать, select_account - для выбора аккаунта, none - для автоматического входа, если пользователь уже зарегался, хз как оно должно работать)
}
Данные закодированы в URI-запроса
Пользователь в новом окошке ставит нужные галочки, прописывает логин и пароль, далее OAuth2-сервер делает запрос на мой redirect_uri, куда отправляет код
2)Мой бэкенд получает следующие данные (также отправленные в URI):
{
    code: "Какой-то одноразовый код", - код подтверждения, который OAuth2 отправляет на мой бэкенд
    state: "таже случайная строка" - если он отличается от до этого сгенерированного state, значит CSRF-атака
    error(опционально): "0x00" - код ошибки (пользователь отменил запрос, неверный логин/пароль)
    error_description: "User gives a shit to you" - описание ошибки
}
3)Бэкенд с этим кодом отправляет запрос на другой oauth2-сервер (например, https://oauth2.googleapis.com/token) данные,
но уже в теле запроса с MIME-типом application/xxx-form-urlencoded:
{
    code: "Код" - полученный код подтверждения (ранее описан)
    client_id: "ID моего приложения в Google/VK БД", - также описан ранее
    client_secret: "Секретный ключ", - хранится на бекенде, именно он подтверждает, что на oauth2-сервер отправил данные мой бэкенд
    redirect_uri: "https://myweb/authorize" - это уже чтобы oauth2-сервер определял, совпадает ли запрос с моего фронтенда с моим бэкендом
    grant_type: "authorization_code" - мы делаем запрос на авторизацию
}
4)В ответ бэкенд получает следующий JSON:
{
    access_token: "аыфьафщыв", - токен для дальнейших запросов для данных Google (например, определения sub)
    expires_in: "1242314", - время жизни токен в секундах
    refresh_token: "dfdf", - мы его не получаем, потому что access_type: online
    scope: {}, - список прав, которые мне сервер реально предоставил
    token_type: "Bearer" - Указывает как использовать токен (в текущей ситуации в HTTP-заголовке Authorization: Bearer <token>)
}
"""

app = FastAPI()

# Хранилище выданных кодов (в памяти, для тестов)
issued_codes = {}

def generate_code(provider: str, client_id: str) -> str:
    return f"{provider}_code_{client_id}_{random.randint(10000, 99999)}"

#@app.get("/health")
#async def health():
#    print(r"GOT REQUEST ON /HEALTH")
#    return Response(status_code=200)

@app.get("/{provider}/authorize")
async def authorize(
    request: Request,
    provider: str,
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    scope: str = Query(""),
    state: str = Query(None),
    error: str = Query(None)
):
    """
    Эмулирует endpoint authorize (редирект на callback с code).
    Поддерживает эмуляцию ошибок через параметр ?error=...
    """
    if error:
        # Эмуляция ошибки авторизации (например, пользователь отменил вход)
        return RedirectResponse(
            url=f"{redirect_uri}?error={error}&state={state or ''}",
            status_code=302
        )

    code = generate_code(provider, client_id)
    issued_codes[code] = {
        "provider": provider,
        "client_id": client_id,
        "scope": scope,
        "state": state,
        "issued_at": time.time()
    }

    # Формируем URL с кодом
    query_params = {
        "code": code,
        "state": state or ""
    }
    redirect_url = f"{redirect_uri}?{urllib.parse.urlencode(query_params)}"
    return RedirectResponse(url=redirect_url, status_code=302)


@app.post("/{provider}/token")
async def token(
    request: Request,
    provider: str,
    code: str = Query(...),
    client_id: str = Query(...),
    client_secret: str = Query(...),
    grant_type: str = Query("authorization_code"),
    redirect_uri: str = Query(...)
):
    """
    Эмулирует endpoint token (обмен code на access_token).
    Можно эмулировать ошибки через query-параметр ?error=...
    """
    error = request.query_params.get("error")
    if error:
        # Возвращаем ошибку как в реальном OAuth2
        return JSONResponse(
            content={"error": error, "error_description": "Mocked error for testing"},
            status_code=400
        )

    if code not in issued_codes:
        raise HTTPException(status_code=400, detail="invalid_code")

    data = issued_codes[code]
    if data["client_id"] != client_id:
        raise HTTPException(status_code=400, detail="invalid_client")

    # Эмуляция задержки (опционально)
    delay = request.query_params.get("delay")
    if delay:
        time.sleep(float(delay))

    # Генерируем фейковый токен
    access_token = f"{provider}_access_token_{client_id}_{code}"
    refresh_token = f"{provider}_refresh_token_{code}" if provider == "google" else None

    response = {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": data["scope"]
    }
    if refresh_token:
        response["refresh_token"] = refresh_token

    # Специфичные поля для VK / Google (опционально, чтобы было похоже на реальные ответы)
    if provider == "vk":
        response["user_id"] = 123456789
        response["email"] = "user@vk.com"
    elif provider == "google":
        response["id_token"] = f"{provider}_id_token_{code}"
        response["expires_in"] = 3599

    return JSONResponse(content=response)


@app.get("/health")
async def health():
    return {"status": "ok"}
