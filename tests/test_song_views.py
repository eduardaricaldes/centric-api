def create_song_with_chords(client, title="Com Cifra"):
    response = client.post(
        "/songs/",
        json={
            "title": title,
            "lyrics": "ignorada",
            "chordpro": "[G]Graça que me [D]alcançou",
            "tone": "G",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_nao_musico_recebe_letra_por_padrao_e_pode_pedir_cifra(client):
    create_song_with_chords(client)

    default_item = client.get("/songs/").json()["items"][0]
    assert default_item["lyrics"] == "Graça que me alcançou"
    assert "chordpro" not in default_item

    chords_item = client.get("/songs/", params={"view": "chords"}).json()["items"][0]
    assert chords_item["chordpro"] == "[G]Graça que me [D]alcançou"
    assert "lyrics" not in chords_item


def test_musico_recebe_cifra_por_padrao_e_pode_pedir_letra(
    client,
    current_user,
    db_session,
):
    create_song_with_chords(client)
    current_user.prefers_chords = True
    db_session.commit()

    default_item = client.get("/songs/").json()["items"][0]
    assert default_item["chordpro"] == "[G]Graça que me [D]alcançou"
    assert "lyrics" not in default_item

    lyrics_item = client.get("/songs/", params={"view": "lyrics"}).json()["items"][0]
    assert lyrics_item["lyrics"] == "Graça que me alcançou"
    assert "chordpro" not in lyrics_item


def test_view_chords_cai_para_letra_quando_nao_ha_cifra(client):
    response = client.post(
        "/songs/",
        json={"title": "Sem Cifra", "lyrics": "Somente a letra"},
    )
    assert response.status_code == 201

    item = client.get("/songs/", params={"view": "chords"}).json()["items"][0]
    assert item["chordpro"] == "Somente a letra"
    assert "lyrics" not in item


def test_detalhe_da_musica_sempre_traz_letra_e_cifra(client):
    song = create_song_with_chords(client)

    for view in ("lyrics", "chords"):
        response = client.get(f"/songs/{song['id']}", params={"view": view})
        assert response.status_code == 200
        assert response.json()["lyrics"] == "Graça que me alcançou"
        assert response.json()["chordpro"] == "[G]Graça que me [D]alcançou"


def test_view_invalida_retorna_422(client):
    assert client.get("/songs/", params={"view": "tabs"}).status_code == 422


def test_transpose_muda_cifra_e_tom_na_listagem(client):
    create_song_with_chords(client)

    item = client.get(
        "/songs/",
        params={"view": "chords", "transpose": 2},
    ).json()["items"][0]

    assert item["chordpro"] == "[A]Graça que me [E]alcançou"
    assert item["tone"] == "A"
    assert "lyrics" not in item

    original = client.get(
        "/songs/",
        params={"view": "chords"},
    ).json()["items"][0]
    assert original["chordpro"] == "[G]Graça que me [D]alcançou"
    assert original["tone"] == "G"


def test_transpose_no_detalhe_preserva_letra_e_muda_cifra_e_tom(client):
    song = create_song_with_chords(client)

    response = client.get(
        f"/songs/{song['id']}",
        params={"view": "chords", "transpose": -2},
    )

    assert response.status_code == 200
    assert response.json()["lyrics"] == "Graça que me alcançou"
    assert response.json()["chordpro"] == "[F]Graça que me [C]alcançou"
    assert response.json()["tone"] == "F"


def test_transpose_exige_visualizacao_de_cifra(client):
    song = create_song_with_chords(client)

    list_response = client.get(
        "/songs/",
        params={"view": "lyrics", "transpose": 2},
    )
    detail_response = client.get(
        f"/songs/{song['id']}",
        params={"transpose": 2},
    )

    assert list_response.status_code == 422
    assert detail_response.status_code == 422


def test_musico_pode_transpor_sem_view_explicita(
    client,
    current_user,
    db_session,
):
    create_song_with_chords(client)
    current_user.prefers_chords = True
    db_session.commit()

    item = client.get("/songs/", params={"transpose": 2}).json()["items"][0]

    assert item["chordpro"] == "[A]Graça que me [E]alcançou"
    assert item["tone"] == "A"


def test_transpose_aceita_apenas_intervalo_de_menos_11_a_11(client):
    create_song_with_chords(client)

    for semitones in (-11, 11):
        response = client.get(
            "/songs/",
            params={"view": "chords", "transpose": semitones},
        )
        assert response.status_code == 200

    for semitones in (-12, 12):
        response = client.get(
            "/songs/",
            params={"view": "chords", "transpose": semitones},
        )
        assert response.status_code == 422


def test_detalhe_em_chords_sem_cifra_cai_para_letra(client):
    create_response = client.post(
        "/songs/",
        json={"title": "Sem Cifra", "lyrics": "Somente a letra", "tone": "C"},
    )
    song_id = create_response.json()["id"]

    response = client.get(
        f"/songs/{song_id}",
        params={"view": "chords", "transpose": 2},
    )

    assert response.status_code == 200
    assert response.json()["lyrics"] == "Somente a letra"
    assert response.json()["chordpro"] == "Somente a letra"
    assert response.json()["tone"] == "D"


def test_playlist_respeita_view_no_detalhe_e_na_rota_aninhada(
    client,
    playlist_id,
):
    song = create_song_with_chords(client)
    add_response = client.post(
        f"/playlist/{playlist_id}/songs/",
        json={"song_id": song["id"]},
    )
    assert add_response.status_code == 201

    endpoints = (
        (f"/playlist/{playlist_id}", lambda body: body["songs"][0]["song"]),
        (f"/playlist/{playlist_id}/songs/", lambda body: body[0]["song"]),
    )

    for endpoint, get_song in endpoints:
        chords_song = get_song(client.get(endpoint, params={"view": "chords"}).json())
        assert chords_song["chordpro"] == "[G]Graça que me [D]alcançou"
        assert "lyrics" not in chords_song

        lyrics_song = get_song(client.get(endpoint, params={"view": "lyrics"}).json())
        assert lyrics_song["lyrics"] == "Graça que me alcançou"
        assert "chordpro" not in lyrics_song


def test_playlist_usa_preferencia_de_musico_sem_view_explicita(
    client,
    playlist_id,
    current_user,
    db_session,
):
    song = create_song_with_chords(client)
    client.post(
        f"/playlist/{playlist_id}/songs/",
        json={"song_id": song["id"]},
    )
    current_user.prefers_chords = True
    db_session.commit()

    detail_song = client.get(f"/playlist/{playlist_id}").json()["songs"][0]["song"]
    nested_song = client.get(f"/playlist/{playlist_id}/songs/").json()[0]["song"]

    for response_song in (detail_song, nested_song):
        assert response_song["chordpro"] == "[G]Graça que me [D]alcançou"
        assert "lyrics" not in response_song
