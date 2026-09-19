def test_get_me_retorna_perfil_atual(client):
    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "name": "Admin",
        "email": "admin@comunidadenorth.com",
        "role": "ADMIN",
        "prefers_chords": False,
    }


def test_get_me_exige_autenticacao(unauthenticated_client):
    response = unauthenticated_client.get("/auth/me")

    assert response.status_code == 401


def test_usuario_pode_alterar_o_proprio_perfil_de_musico(client):
    response = client.patch("/auth/me", json={"prefers_chords": True})

    assert response.status_code == 200
    assert response.json()["prefers_chords"] is True
    assert client.get("/auth/me").json()["prefers_chords"] is True


def test_usuario_pode_se_registrar_como_musico(client):
    response = client.post(
        "/auth/register",
        json={
            "name": "Musicista",
            "email": "musicista@example.com",
            "password": "senha-segura",
            "prefers_chords": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["prefers_chords"] is True
    assert response.json()["role"] == "MEMBER"
