"""SpeedStart CMD encoding and strict ASM86 H86 input handling."""
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'base'

def transform(data, masks):
    """Transform only the stored CODE group; masks are little-endian byte order."""
    if len(data) < 128 or not masks:
        raise ValueError("missing CMD header or XOR mask")
    result = bytearray(data)
    offset = 128
    found = False
    for i in range(8):
        kind = data[i*9]
        if not kind:
            break
        size = int.from_bytes(data[i*9+1:i*9+3], 'little') * 16
        if offset + size > len(data):
            raise ValueError('truncated CMD group')
        if kind == 1:
            if found:
                raise ValueError('multiple CODE groups')
            found = True
            for j in range(size):
                result[offset+j] ^= masks[j % len(masks)]
        offset += size
    if not found:
        raise ValueError('missing CODE group')
    return bytes(result)


def records(path):
    result = {}
    eof = False
    for line in path.read_bytes().splitlines():
        if not line.startswith(b':'):
            continue
        n = int(line[1:3], 16)
        raw = bytes.fromhex(line[1:1+(n+5)*2].decode('ascii'))
        if len(raw) != n+5 or sum(raw) % 256:
            raise ValueError(f'{path}: bad H86 record')
        if raw[3] == 1:
            eof = True
            break  # remaining bytes are CP/M record padding
        if raw[3] == 3:
            continue
        if raw[3] != 0x81:
            raise ValueError('unexpected non-CODE record')
        address = int.from_bytes(raw[1:3], 'big')
        for a, value in enumerate(raw[4:4+n], address):
            if a in result:
                raise ValueError('overlapping H86 records')
            result[a] = value
    if not eof or not result:
        raise ValueError('incomplete H86 output')
    return result


def assembled(path, start, end):
    data = records(path)
    if set(data) != set(range(start, end)):
        raise ValueError(f'{path}: incomplete or excess assembly coverage')
    return bytes(data[a] for a in range(start, end))


def write(path, data):
    """Avoid changing timestamps when the content is already current."""
    if not path.exists() or path.read_bytes() != data:
        path.write_bytes(data)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind', choices=['kernel', 'application'])
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    data = args.input.read_bytes()
    if args.kind == 'application' and (len(data) < 128 or data[0] != 1):
        parser.error('SpeedStart requires CODE as the first application group')
    write(args.output, transform(data, [255] if args.kind == 'kernel' else [0xb4, 0xa5]))
