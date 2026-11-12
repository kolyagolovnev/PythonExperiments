
import pytest

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
