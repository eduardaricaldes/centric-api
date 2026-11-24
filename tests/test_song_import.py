import io
import zipfile

import pytest

from app.main import app
from app.services.ai_service import AIServiceUnavailableError
from app.services.song_import import (
    ImportedSong,
    detect_import_file,
    docx_to_text,
    get_song_import_provider,
    tidy_lyrics,
)


class FakeProvider:
    def __init__(self, song=None, error=None):
        self.song = song
        self.error = error
        self.files = []

    def extract(self, file):
        self.files.append(file)
        if self.error:
            raise self.error
        return self.song


@pytest.fixture()
def use_provider():
    def configure(provider):
        app.dependency_overrides[get_song_import_provider] = lambda: provider
        return provider

    yield configure
    app.dependency_overrides.pop(get_song_import_provider, None)


def make_docx(paragraphs):
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    xml = f'<?xml version="1.0"?><w:document xmlns:w="{ns}"><w:body>{body}</w:body></w:document>'
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


def test_importar_pdf_devolve_rascunho_sem_salvar(client, use_provider):
    provider = use_provider(
        FakeProvider(ImportedSong("Ele é a Glória", "Gabriela Rocha", "G", "[G]Ele é a [D]glória\n\n\n{comment: Refrão}\nSanto"))
    )

    response = client.post(
        "/songs/import",
        files={"file": ("ele-e-a-gloria.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Ele é a Glória"
    assert data["artist"] == "Gabriela Rocha"
    assert data["tone"] == "G"
    assert data["chordpro"] == "[G]Ele é a [D]glória\n\n{comment: Refrão}\nSanto"
    assert data["lyrics"].startswith("Ele é a glória")
    assert data["used_ai"] is True
    assert provider.files[0].kind == "pdf"
    assert provider.files[0].text is None

    # Nada foi salvo.
    assert client.get("/songs/").json()["total"] == 0


def test_txt_sem_ia_usa_texto_e_nome_do_arquivo(client, use_provider):
    use_provider(FakeProvider(error=AIServiceUnavailableError("sem chave")))

    response = client.post(
        "/songs/import",
        files={"file": ("Bondade_de_Deus.txt", "Te amo, Deus\n\n\n\nTua bondade".encode(), "text/plain")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Bondade de Deus"
    assert data["chordpro"] == "Te amo, Deus\n\nTua bondade"
    assert data["used_ai"] is False


def test_foto_sem_ia_devolve_503(client, use_provider):
    use_provider(FakeProvider(error=AIServiceUnavailableError("sem chave")))

    response = client.post(
        "/songs/import",
        files={"file": ("foto.jpg", b"\xff\xd8\xff", "image/jpeg")},
    )

    assert response.status_code == 503


def test_formato_nao_aceito_devolve_415(client, use_provider):
    use_provider(FakeProvider())
    response = client.post("/songs/import", files={"file": ("planilha.xlsx", b"x", "application/octet-stream")})
    assert response.status_code == 415

    response = client.post("/songs/import", files={"file": ("antigo.doc", b"x", "application/msword")})
    assert response.status_code == 415
    assert ".docx" in response.json()["detail"]


def test_arquivo_maior_que_10mb_devolve_413(client, use_provider):
    use_provider(FakeProvider())
    big = b"a" * (10 * 1024 * 1024 + 1)
    response = client.post("/songs/import", files={"file": ("grande.txt", big, "text/plain")})
    assert response.status_code == 413


def test_word_vira_texto_para_a_ia(client, use_provider):
    provider = use_provider(FakeProvider(ImportedSong("Rendido", None, None, "Rendido estou")))
    data = make_docx(["Rendido estou", "", "Aos teus pés"])

    response = client.post("/songs/import", files={"file": ("rendido.docx", data, "application/octet-stream")})

    assert response.status_code == 200
    assert provider.files[0].kind == "docx"
    assert provider.files[0].text == "Rendido estou\n\nAos teus pés"


def test_docx_to_text_le_paragrafos():
    assert docx_to_text(make_docx(["A", "B"])) == "A\nB"


def test_detecta_imagem_pelo_content_type():
    assert detect_import_file("sem-extensao", "image/png", b"x").kind == "image"


def test_tidy_lyrics_junta_linhas_em_branco():
    assert tidy_lyrics("  \nA  \r\n\r\n\r\nB\n\n") == "A\n\nB"
