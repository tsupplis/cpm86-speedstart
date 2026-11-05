"""Verify frozen references, complete source coverage, encoding and disk layout."""
import hashlib
from encode import ROOT, BASE, transform, assembled
from image import payloads, padded, filesystem, allocation

REFERENCES = {'boot-sector.bin': 'dc3aed33bd9297b143ed8ef4d70a0b4aa31807be0a138da185698ac8d561b487', 'msbasic.cmd': 'e61761de242da44e5c3376dd08de96c72159a618a8e8927319aca2e7edda23a3', 'speed.str': '777c5baf5f28fe777e3f57a397dac44fdd764fdf5598c21a6584e7c5c30de127', 'track0-sector9.bin': 'e88420334db238995376ef429fff1ebfdfb538d26d702f39f9e92f0704c50ff9'}


def check():
    for name, digest in REFERENCES.items():
        assert hashlib.sha256((BASE/name).read_bytes()).hexdigest() == digest, name
    k = ROOT/'kernel'
    reference = transform((BASE/'speed.str').read_bytes(), [255])
    assert (k/'speed.dec').read_bytes() == reference
    assert (k/'speed.str').read_bytes() == (BASE/'speed.str').read_bytes()
    for name, start, end in [('ccp', 0, 0xa00), ('bdos', 0xa00, 0x2500),
                             ('bios', 0x2500, 0x3f80)]:
        assert assembled(k/(name+'.h86'), start, end) == reference[128+start:128+end]
    decoded = bytearray(reference)
    decoded[128+9:128+0x16] = b'\x7f\x0aA:MBASIC86\0'
    encoded = (k/'basic.str').read_bytes()
    assert (k/'basic.dec').read_bytes() == decoded
    assert transform(encoded, [255]) == decoded
    app = (BASE/'msbasic.cmd').read_bytes()
    stm = (ROOT/'msbasic.stm').read_bytes()
    assert transform(stm, [0xb4, 0xa5]) == app
    assert stm[:128] == app[:128]
    code_end = 128 + int.from_bytes(app[1:3], 'little')*16
    assert stm[code_end:] == app[code_end:]
    image = (ROOT/'stm-basic.img').read_bytes()
    assert len(image) == 184320
    # Independent PCE parser verifies the IMD sector IDs and mixed geometry.
    assert padded(payloads(ROOT/'stm-basic.imd')) == image
    boot = bytearray((BASE/'boot-sector.bin').read_bytes())
    boot[0x40:0x66] = b'This is a SpeedStart BASIC data disk. '
    loader = bytearray((BASE/'track0-sector9.bin').read_bytes())
    loader[0xbb:0xd1] = b'Loading MBASIC-86... \0'
    assert image[:512] == boot == (k/'basic-boot.bin').read_bytes()
    assert image[4096:4608] == loader == (k/'basic-loader.bin').read_bytes()
    fs = filesystem(image)
    expected = [('SPEED.STR', encoded), ('MBASIC86.STM', stm)]
    for name, data in expected:
        extracted = b''.join(fs[a:a+n] for a,n in allocation(fs, name))
        assert extracted == data + b'\x1a'*((-len(data)) % 128), name
    assert allocation(fs, 'SPEED.STR') == [(4096+n*1024, 1024) for n in range(2,18)]
    names = set()
    for i in range(64):
        entry = fs[4096+i*32:4096+(i+1)*32]
        if entry[0] == 0xe5:
            continue
        assert entry[0] == 0
        assert entry[9] & 128 and entry[10] & 128
        names.add(bytes(v & 127 for v in entry[1:12]))
    assert names == {b'SPEED   STR', b'MBASIC86STM'}
    assert fs[512:4096] == b'\xe5'*(4096-512)
    print('PASS: original hashes; complete assembled kernel and boot sectors')
    print('PASS: only the three intended BASIC overlays; CMD encoding round trips')
    print('PASS: raw/IMD sector payloads; fixed kernel allocation; BASIC file extents')


if __name__ == '__main__':
    check()
