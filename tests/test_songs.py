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


def test_lista_de_categorias(client):
    response = client.get("/songs/categories")
    assert response.status_code == 200
    assert "Adoração" in response.json()


def test_criar_musica_com_categoria_fora_da_lista_da_422(client):
    response = client.post("/songs/", json={"title": "T", "lyrics": "L", "category": "Rock"})
    assert response.status_code == 422


def test_criar_musica_com_categoria_da_lista(client):
    response = client.post("/songs/", json={"title": "T", "lyrics": "L", "category": "Ceia"})
    assert response.status_code == 201
    assert response.json()["category"] == "Ceia"


def test_categoria_vazia_vira_sem_categoria(client):
    response = client.post("/songs/", json={"title": "T", "lyrics": "L", "category": ""})
    assert response.status_code == 201
    assert response.json()["category"] is None


def test_musica_com_categoria_antiga_continua_editavel(client, db_session):
    """Músicas de antes da lista fechada guardam texto livre: editar a letra não pode quebrar."""
    from app.models.song import Song

    song = Song(title="Antiga", lyrics="L", category="adoracao livre")
    db_session.add(song)
    db_session.commit()

    response = client.patch(f"/songs/{song.id}", json={"lyrics": "Nova", "category": "adoracao livre"})
    assert response.status_code == 200

    response = client.patch(f"/songs/{song.id}", json={"category": "Outra livre"})
    assert response.status_code == 422

    response = client.patch(f"/songs/{song.id}", json={"category": "Adoração"})
    assert response.status_code == 200
    assert response.json()["category"] == "Adoração"


def test_filtrar_listagem_por_categoria(client, song_ids):
    client.post("/songs/", json={"title": "Pão da Vida", "lyrics": "L", "category": "Ceia"})
    response = client.get("/songs/", params={"category": "Ceia"})
    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == ["Pão da Vida"]


def test_mesmo_titulo_ignora_acento_e_caixa(client):
    client.post("/songs/", json={"title": "Ele é a Glória", "lyrics": "L"})
    client.post("/songs/", json={"title": "Ele", "lyrics": "L"})

    response = client.get("/songs/same-title", params={"title": "ele e a gloria!"})

    assert response.status_code == 200
    assert [item["title"] for item in response.json()] == ["Ele é a Glória"]


def test_slides_ajustados_sao_salvos_e_voltam_ao_automatico_quando_a_letra_muda(client):
    song = client.post("/songs/", json={"title": "S", "lyrics": "A\nB\n\nC"}).json()
    assert song["slides"] is None

    response = client.patch(f"/songs/{song['id']}", json={"slides": "A\n\nB\nC"})
    assert response.status_code == 200
    assert response.json()["slides"] == "A\n\nB\nC"

    # Editar só o título mantém os slides.
    response = client.patch(f"/songs/{song['id']}", json={"title": "S2"})
    assert response.json()["slides"] == "A\n\nB\nC"

    # Mudar a letra sem mandar slides volta ao automático.
    response = client.patch(f"/songs/{song['id']}", json={"lyrics": "Nova"})
    assert response.json()["slides"] is None


def test_slides_vazios_viram_automatico(client):
    song = client.post("/songs/", json={"title": "S", "lyrics": "A", "slides": "  "}).json()
    assert song["slides"] is None


def test_versoes_da_musica_por_artista(client):
    """Card "versões": a mesma música com artista, tom e arranjo próprios."""
    original = client.post(
        "/songs/",
        json={"title": "Ele é a Glória", "lyrics": "L", "artist": "Gabriela Rocha", "tone": "A"},
    ).json()
    banda = client.post(
        "/songs/",
        json={
            "title": "Ele é a Glória",
            "lyrics": "L",
            "artist": "Matheus Rizzo",
            "tone": "G",
            "arrangement": "Começa só voz e violão; banda entra no refrão.",
        },
    ).json()
    assert banda["arrangement"].startswith("Começa")

    versions = client.get("/songs/same-title", params={"title": "Ele é a Glória"}).json()
    assert {(v["artist"], v["tone"]) for v in versions} == {("Gabriela Rocha", "A"), ("Matheus Rizzo", "G")}
    assert {v["id"] for v in versions} == {original["id"], banda["id"]}
