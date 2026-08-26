from pathlib import Path


TYP_PATH = Path('styles/uralla.txt')
TARGET_TYPES = {'0x1341f', '0x1341d', '0x1616', '0x1615'}


def _point_blocks(text: str):
    blocks = []
    current = None
    for line in text.splitlines():
        if line.strip().lower() == '[_point]':
            current = []
        elif line.strip().lower() == '[end]':
            if current is not None:
                blocks.append(current)
                current = None
        elif current is not None:
            current.append(line)
    return blocks


def test_technical_rail_and_traffic_types_are_nolabel():
    text = TYP_PATH.read_text(encoding='cp1251')
    found = set()

    for block in _point_blocks(text):
        type_code = None
        font_style = None
        for line in block:
            stripped = line.strip()
            if stripped.lower().startswith('type='):
                type_code = stripped.split('=', 1)[1].lower()
            elif stripped.lower().startswith('fontstyle='):
                font_style = stripped.split('=', 1)[1].strip().lower()

        if type_code in TARGET_TYPES:
            found.add(type_code)
            assert font_style == 'nolabel', f'{type_code} must use FontStyle=NoLabel'

    assert found == TARGET_TYPES, f'missing point types: {sorted(TARGET_TYPES - found)}'
