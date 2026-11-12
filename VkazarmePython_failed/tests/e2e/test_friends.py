
import pytest
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
