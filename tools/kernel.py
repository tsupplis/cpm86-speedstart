"""Join complete assembled sources and apply the three explicit BASIC data overlays."""
from encode import ROOT, assembled, transform, write

K = ROOT/'kernel'
PARTS = [('ccp', 0, 0xa00), ('bdos', 0xa00, 0x2500), ('bios', 0x2500, 0x3f80)]


def overlay(original, name, origin, start, end):
    data = assembled(K/(name+'.h86'), start, end)
    result = bytearray(original)
    result[start-origin:end-origin] = data
    return bytes(result)


def build():
    boot = assembled(K/'boot.h86', 0x7c00, 0x7e00)
    loader = assembled(K/'loader.h86', 0x7800, 0x7a00)
    header = assembled(K/'header.h86', 0, 128)
    code = b''.join(assembled(K/(name+'.h86'), start, end) for name,start,end in PARTS)
    decoded = header + code
    write(K/'boot.bin', boot)
    write(K/'loader.bin', loader)
    write(K/'speed.dec', decoded)
    write(K/'speed.str', transform(decoded, [255]))
    basic = header + overlay(code, 'basccp', 0, 9, 0x16)
    write(K/'basic.dec', basic)
    write(K/'basic.str', transform(basic, [255]))
    write(K/'basic-boot.bin', overlay(boot, 'basboot', 0x7c00, 0x7c40, 0x7c66))
    write(K/'basic-loader.bin', overlay(loader, 'basload', 0x7800, 0x78bb, 0x78d1))


if __name__ == '__main__':
    build()
