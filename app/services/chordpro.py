import re

SHARPS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
FLATS  = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']

_CHORD_RE = re.compile(r'\[([^\]]*)\]')


def to_plain_lyrics(chordpro: str) -> str:
    lines = []
    for line in chordpro.splitlines():
        lines.append(_CHORD_RE.sub('', line).strip())
    return '\n'.join(lines)


def _parse_root(chord: str) -> tuple[str, str]:
    if len(chord) >= 2 and chord[1] in ('#', 'b'):
        return chord[:2], chord[2:]
    return chord[0], chord[1:]


def _transpose_root(root: str, semitones: int) -> str:
    use_flats = len(root) == 2 and root[1] == 'b'
    scale = FLATS if use_flats else SHARPS
    other = SHARPS if use_flats else FLATS

    try:
        idx = scale.index(root)
    except ValueError:
        try:
            idx = other.index(root)
        except ValueError:
            return root  # não é nota conhecida, devolve intacto

    return scale[(idx + semitones) % 12]


def _transpose_chord(chord: str, semitones: int) -> str:
    if not chord:
        return chord
    if '/' in chord:
        base, bass = chord.split('/', 1)
        return f'{_transpose_chord(base, semitones)}/{_transpose_chord(bass, semitones)}'
    root, suffix = _parse_root(chord)
    return _transpose_root(root, semitones) + suffix


def transpose(chordpro: str, semitones: int) -> str:
    return _CHORD_RE.sub(
        lambda m: f'[{_transpose_chord(m.group(1), semitones)}]',
        chordpro,
    )
