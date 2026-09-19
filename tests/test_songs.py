def test_max_length_do_artist_e_validado(client):
    """Regressão: os campos opcionais eram tuplas e o Field era ignorado."""
    response = client.post(
        "/songs/",
        json={"title": "T", "lyrics": "L", "artist": "A" * 300},
    )
    assert response.status_code == 422


def test_busca_por_titulo(client, song_ids):
    response = client.get("/songs/", params={"search": "Ousado"})
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_create_com_chordpro_regenera_lyrics(client):
    cp = "[G]Antes de eu [D]falar"
    response = client.post(
        "/songs/",
        json={"title": "Teste", "lyrics": "ignorado", "chordpro": cp},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["lyrics"] == "Antes de eu falar"
    assert data["chordpro"] == cp


def test_patch_com_chordpro_regenera_lyrics(client):
    create = client.post(
        "/songs/",
        json={"title": "Teste Patch", "lyrics": "letra original"},
    )
    song_id = create.json()["id"]

    cp = "[Em]Tu já [C]sabes"
    patch = client.patch(f"/songs/{song_id}", json={"chordpro": cp})
    assert patch.status_code == 200
    assert patch.json()["lyrics"] == "Tu já sabes"
    assert patch.json()["chordpro"] == cp


def test_create_sem_chordpro_mantem_lyrics(client):
    response = client.post(
        "/songs/",
        json={"title": "Sem Cifra", "lyrics": "letra manual"},
    )
    assert response.status_code == 201
    assert response.json()["lyrics"] == "letra manual"
    assert response.json()["chordpro"] is None
