from app.services.chordpro import to_plain_lyrics, transpose


# ── to_plain_lyrics ──────────────────────────────────────────────────────────

def test_plain_removes_chords():
    assert to_plain_lyrics("[G]Antes de eu [D]falar") == "Antes de eu falar"

def test_plain_preserves_line_breaks():
    cp = "[G]Linha um\n[D]Linha dois"
    assert to_plain_lyrics(cp) == "Linha um\nLinha dois"

def test_plain_chord_only_line_becomes_empty():
    cp = "[G] [D] [Em]\nLetra aqui"
    lines = to_plain_lyrics(cp).split('\n')
    assert lines[0] == ''
    assert lines[1] == 'Letra aqui'

def test_plain_no_chords_unchanged():
    assert to_plain_lyrics("Aleluia") == "Aleluia"


# ── transpose ────────────────────────────────────────────────────────────────

def test_transpose_up_one():
    assert transpose("[G]texto", 1) == "[G#]texto"

def test_transpose_B_wraps_to_C():
    assert transpose("[B]texto", 1) == "[C]texto"

def test_transpose_C_wraps_down_to_B():
    assert transpose("[C]texto", -1) == "[B]texto"

def test_transpose_sharp_to_natural():
    assert transpose("[F#]texto", 1) == "[G]texto"

def test_transpose_flat_plus_two():
    assert transpose("[Bb]texto", 2) == "[C]texto"

def test_transpose_preserves_suffix():
    assert transpose("[Am7]texto", 2) == "[Bm7]texto"

def test_transpose_slash_chord():
    assert transpose("[C/E]texto", 2) == "[D/F#]texto"

def test_transpose_negative():
    assert transpose("[D]texto", -2) == "[C]texto"

def test_transpose_full_verse():
    cp = "[G]Antes de eu [D]falar\n[Em]Tu já [C]sabes"
    assert transpose(cp, 2) == "[A]Antes de eu [E]falar\n[F#m]Tu já [D]sabes"

def test_transpose_flat_output_stays_flat():
    # Eb + 2 → F (still natural, not E#)
    assert transpose("[Eb]texto", 2) == "[F]texto"

def test_transpose_full_octave_returns_same():
    assert transpose("[G]texto", 12) == "[G]texto"
