import io

def test_upload_media(client, headers):
    # Given: файл для загрузки
    file_content = b"fake image content"
    files = {"file": ("avatar.jpg", file_content, "image/jpeg")}

    # When: загружаем медиа
    resp = client.post("/media", files=files, headers=headers)
    # Then: загрузка успешна
    assert resp.status_code in (200, 201)
