import pytest

def test_paste_and_comment(client, headers, auth_token):
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
