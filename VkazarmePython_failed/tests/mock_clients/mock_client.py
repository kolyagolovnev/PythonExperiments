import requests
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict, Any

class OAuthTestClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        # Увеличим таймаут, чтобы тесты не падали из-за эмуляции задержек на моке
        self.timeout = 10 

    def _get_provider_url(self, provider: str, endpoint: str) -> str:
        return f"{self.base_url}/{provider}/{endpoint}"

    def simulate_authorize_flow(
        self, 
        provider: str, 
        client_id: str, 
        redirect_uri: str, 
        scope: str = "email profile",
        state: str = "test-state-123",
        simulate_error: bool = False,
        error_type: str = "access_denied"
    ) -> Optional[str]:
        """
        Эмулирует шаг авторизации: запрашивает /authorize и извлекает 'code' из редиректа.
        Возвращает код авторизации или None, если произошла ошибка.
        """
        url = self._get_provider_url(provider, "authorize")
        
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state
        }

        if simulate_error:
            params["error"] = error_type

        try:
            print(f"[*] Запрос авторизации к {url}...")
            response = self.session.get(url, params=params, allow_redirects=False, timeout=self.timeout)
            
            if response.status_code != 302:
                print(f"[-] Ошибка: Ожидался редирект (302), получен {response.status_code}")
                return None

            location = response.headers.get("Location")
            if not location:
                print("[-] Ошибка: Нет заголовка Location в редиректе")
                return None

            # Парсим query параметры из URL редиректа
            parsed_url = urlparse(location)
            query_params = parse_qs(parsed_url.query)

            if "error" in query_params:
                error_msg = query_params["error"][0]
                print(f"[!] Пользователь отменил вход или ошибка: {error_msg}")
                return None
            
            code = query_params.get("code")
            if code:
                code_val = code[0]
                print(f"[+] Успешно получен код: {code_val}")
                return code_val
            else:
                print("[-] Ошибка: Код не найден в редиректе")
                return None

        except requests.exceptions.RequestException as e:
            print(f"[-] Сетевая ошибка: {e}")
            return None

    def exchange_code_for_tokens(
        self,
        provider: str,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        is_new_user: bool = False,
        simulate_token_error: Optional[str] = None,
        delay: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Обменивает код на access_token и id_token.
        Поддерживает эмуляцию ошибок и флага new_user.
        """
        url = self._get_provider_url(provider, "token")
        
        params = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri
        }

        if simulate_token_error:
            params["error"] = simulate_token_error
        
        if is_new_user:
            params["new_user"] = "true"
            
        if delay:
            params["delay"] = str(delay)

        print(f"[*] Обмен кода на токены: {url}...")
        
        try:
            response = self.session.post(url, data=params, timeout=self.timeout)
            
            if response.status_code >= 400:
                print(f"[-] Ошибка сервера (статус {response.status_code}): {response.text}")
                return {"success": False, "error": response.json()}

            data = response.json()
            print("[+] Токены получены успешно!")
            return {"success": True, "data": data}

        except requests.exceptions.Timeout:
            print("[-] Ошибка: Превышено время ожидания (таймаут)")
            return {"success": False, "error": "timeout"}
        except Exception as e:
            print(f"[-] Неожиданная ошибка: {e}")
            return {"success": False, "error": str(e)}

# --- Примеры использования ---

if __name__ == "__main__":
    # Конфигурация для теста
    BASE_URL = "http://fake-provider-server:80"
    CLIENT_ID = "test-client-id-123"
    CLIENT_SECRET = "test-secret-456"
    REDIRECT_URI = "http://your-app.com/callback"

    client = OAuthTestClient(BASE_URL)

    print("="*40)
    print("ТЕСТ 1: Успешная авторизация (Google, существующий пользователь)")
    print("="*40)
    code = client.simulate_authorize_flow("google", CLIENT_ID, REDIRECT_URI)
    if code:
        res = client.exchange_code_for_tokens("google", code, CLIENT_ID, CLIENT_SECRET, REDIRECT_URI)
        if res["success"]:
            print(f"Access Token: {res['data'].get('access_token')}")
            print(f"ID Token exists: {'id_token' in res['data']}")

    print("\n" + "="*40)
    print("ТЕСТ 2: Регистрация нового пользователя (Google)")
    print("="*40)
    # Генерируем новый код специально для сценария new_user
    code_new = client.simulate_authorize_flow("google", CLIENT_ID, REDIRECT_URI, state="new-user-flow")
    if code_new:
        res = client.exchange_code_for_tokens("google", code_new, CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, is_new_user=True)
        if res["success"]:
            print(f"Это новый пользователь: {res['data'].get('registration_flow') == 'new_user'}")
            print(f"Refresh Token получен: {'refresh_token' in res['data']}")

    print("\n" + "="*40)
    print("ТЕСТ 3: Ошибка авторизации (пользователь отменил вход)")
    print("="*40)
    client.simulate_authorize_flow("vk", CLIENT_ID, REDIRECT_URI, simulate_error=True, error_type="access_denied")

    print("\n" + "="*40)
    print("ТЕСТ 4: Ошибка обмена кода (invalid_grant)")
    print("="*40)
    res = client.exchange_code_for_tokens("vk", "fake-code-123", CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, simulate_token_error="invalid_grant")
    
    print("\n" + "="*40)
    print("ТЕСТ 5: Эмуляция таймаута сети")
    print("="*40)
    # Используем существующий код (или получим новый), но добавим задержку 5 сек
    # Примечание: для этого теста нужно, чтобы ваш мок-сервер поддерживал параметр delay
    code_delay = client.simulate_authorize_flow("google", CLIENT_ID, REDIRECT_URI)
    if code_delay:
        # Ставим таймаут клиента меньше, чем задержка сервера, чтобы поймать ошибку
        temp_client = OAuthTestClient(BASE_URL)
        temp_client.timeout = 2  # Клиент ждет всего 2 секунды
        res = temp_client.exchange_code_for_tokens("google", code_delay, CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, delay=5.0)
        if not res["success"] and res["error"] == "timeout":
            print("[OK] Таймаут успешно пойман!")
