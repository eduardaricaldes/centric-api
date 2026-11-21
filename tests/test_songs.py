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


def test_busca_sem_resultado_retorna_lista_vazia(client, song_ids):
    response = client.get(
        "/songs/",
        params={"search": "Nao Existe", "page": 2, "limit": 3},
    )

    assert response.status_code == 200
    assert response.json() == {
        "total": 0,
        "page": 2,
        "limit": 3,
        "items": [],
    }


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


def test_excluir_musica_que_esta_em_repertorio_da_409(client, playlist_id, song_ids):
    client.post(f"/playlist/{playlist_id}/songs/", json={"song_id": song_ids[0]})

    response = client.delete(f"/songs/{song_ids[0]}")

    assert response.status_code == 409
    assert response.json()["detail"] == "Song is in a playlist"
    assert client.get(f"/songs/{song_ids[0]}").status_code == 200


def test_excluir_musica_fora_de_repertorio(client, song_ids):
    response = client.delete(f"/songs/{song_ids[1]}")

    assert response.status_code == 204
    assert client.get(f"/songs/{song_ids[1]}").status_code == 404



def _ids_paginados(client, paginas, limit):
    ids = []
    for page in range(1, paginas + 1):
        response = client.get("/songs/", params={"page": page, "limit": limit})
        assert response.status_code == 200
        ids.extend(item["id"] for item in response.json()["items"])
    return ids


def test_editar_letra_nao_muda_a_ordem_da_listagem(client):
    """Regressão: sem ORDER BY, o Postgres devolvia a música editada no fim da
    tabela. Quem já estava paginando via a mesma música em duas páginas (e outra
    sumia), parecendo que a música tinha duplicado."""
    titulos = ["Bondade de Deus", "Aleluia", "Descansarei", "Caminho", "Eu Navegarei", "Faz Chover"]
    ids = {}
    for titulo in titulos:
        response = client.post("/songs/", json={"title": titulo, "lyrics": f"letra de {titulo}"})
        assert response.status_code == 201
        ids[titulo] = response.json()["id"]

    esperado = [ids[t] for t in sorted(titulos)]
    assert _ids_paginados(client, 3, 2) == esperado

    # Editar a letra faz o Postgres gravar uma nova versão da linha no fim da tabela.
    response = client.patch(f"/songs/{ids['Aleluia']}", json={"chordpro": "[G]Letra nova"})
    assert response.status_code == 200

    assert _ids_paginados(client, 3, 2) == esperado
