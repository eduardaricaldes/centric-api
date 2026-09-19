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
