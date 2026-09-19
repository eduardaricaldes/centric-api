def test_cria_e_lista_playlists(client, playlist_id):
    response = client.get("/playlist/")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == playlist_id


def test_get_por_id_traz_playlist_com_letras_na_ordem(client, playlist_id, song_ids):
    for song_id in song_ids:
        client.post(f"/playlist/{playlist_id}/songs/", json={"song_id": song_id})

    response = client.get(f"/playlist/{playlist_id}")
    assert response.status_code == 200

    songs = response.json()["songs"]
    assert [item["position"] for item in songs] == [1, 2, 3, 4]
    assert songs[0]["song"]["title"] == "Ousado Amor"
    assert songs[0]["song"]["lyrics"]


def test_update_parcial_mantem_os_outros_campos(client, playlist_id):
    response = client.put(f"/playlist/{playlist_id}", json={"description": "Culto de Natal"})
    assert response.status_code == 200
    assert response.json()["title"] == "Culto de Domingo à Noite"
    assert response.json()["description"] == "Culto de Natal"


def test_delete_playlist_nao_apaga_musicas_do_catalogo(client, playlist_id, song_ids):
    client.post(f"/playlist/{playlist_id}/songs/", json={"song_id": song_ids[0]})

    assert client.delete(f"/playlist/{playlist_id}").status_code == 204
    assert client.get(f"/playlist/{playlist_id}").status_code == 404
    assert client.get("/songs/").json()["total"] == 4


def test_playlist_inexistente(client):
    assert client.get("/playlist/999").status_code == 404
