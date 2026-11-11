def login(client, email="pm@demo.local", password="demo1234"):
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def login_token(client, email="pm@demo.local", password="demo1234"):
    response = login(client, email, password)
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]["token"]
