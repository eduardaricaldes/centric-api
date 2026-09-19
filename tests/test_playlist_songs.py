def test_adicionar_musicas_numera_as_posicoes(client, playlist_id, song_ids):
    positions = []
    for song_id in song_ids:
        response = client.post(f"/playlist/{playlist_id}/songs/", json={"song_id": song_id})
        assert response.status_code == 201
        positions.append(response.json()["position"])

    assert positions == [1, 2, 3, 4]


def test_adicionar_no_meio_empurra_as_seguintes(client, playlist_id, song_ids):
    for song_id in song_ids[:3]:
        client.post(f"/playlist/{playlist_id}/songs/", json={"song_id": song_id})

    client.post(f"/playlist/{playlist_id}/songs/", json={"song_id": song_ids[3], "position": 2})

    items = client.get(f"/playlist/{playlist_id}/songs/").json()
    assert [item["position"] for item in items] == [1, 2, 3, 4]
    assert items[1]["song_id"] == song_ids[3]


def test_nao_aceita_musica_duplicada(client, playlist_id, song_ids):
    client.post(f"/playlist/{playlist_id}/songs/", json={"song_id": song_ids[0]})
    response = client.post(f"/playlist/{playlist_id}/songs/", json={"song_id": song_ids[0]})
    assert response.status_code == 409


def test_nao_aceita_musica_inexistente(client, playlist_id):
    assert client.post(f"/playlist/{playlist_id}/songs/", json={"song_id": 999}).status_code == 404


def test_mover_musica_para_outra_posicao(client, playlist_id, song_ids):
    items = [
        client.post(f"/playlist/{playlist_id}/songs/", json={"song_id": song_id}).json()
        for song_id in song_ids
    ]
    ultima = items[-1]["id"]

    response = client.patch(f"/playlist/{playlist_id}/songs/{ultima}", json={"position": 1})
    assert response.status_code == 200

    ordem = response.json()
    assert ordem[0]["id"] == ultima
    assert [item["position"] for item in ordem] == [1, 2, 3, 4]


def test_reordenar_playlist_inteira(client, playlist_id, song_ids):
    items = [
        client.post(f"/playlist/{playlist_id}/songs/", json={"song_id": song_id}).json()
        for song_id in song_ids
    ]
    invertida = [item["id"] for item in reversed(items)]

    response = client.put(f"/playlist/{playlist_id}/songs/reorder", json={"item_ids": invertida})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == invertida


def test_reorder_exige_a_lista_completa(client, playlist_id, song_ids):
    for song_id in song_ids:
        client.post(f"/playlist/{playlist_id}/songs/", json={"song_id": song_id})

    items = client.get(f"/playlist/{playlist_id}/songs/").json()
    response = client.put(
        f"/playlist/{playlist_id}/songs/reorder",
        json={"item_ids": [items[0]["id"]]},
    )
    assert response.status_code == 400


def test_remover_musica_renumera_as_posicoes(client, playlist_id, song_ids):
    items = [
        client.post(f"/playlist/{playlist_id}/songs/", json={"song_id": song_id}).json()
        for song_id in song_ids
    ]

    assert client.delete(f"/playlist/{playlist_id}/songs/{items[0]['id']}").status_code == 204

    restantes = client.get(f"/playlist/{playlist_id}/songs/").json()
    assert [item["position"] for item in restantes] == [1, 2, 3]
    assert client.get("/songs/").json()["total"] == 4
