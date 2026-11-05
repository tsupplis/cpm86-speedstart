"""Create the BASIC SpeedStart floppy from assembled components, without a base disk."""
from pathlib import Path
import subprocess
import tempfile
from encode import ROOT, BASE, transform, write

def payloads(path):
    with tempfile.TemporaryDirectory(prefix='stm-sectors-') as folder:
        raw = Path(folder)/'sectors.bin'
        subprocess.run(['psi', str(path), '-O', 'raw', '-o', str(raw)], check=True,
                       capture_output=True)
        return raw.read_bytes()


def padded(raw):
    if len(raw) != 321*512:
        raise ValueError('expected nine sectors on track zero, eight on tracks 1..39')
    out = bytearray(raw[:9*512])
    for c in range(1,40):
        start = (9+(c-1)*8)*512
        out.extend(raw[start:start+8*512])
        out.extend(b'\xe5'*512)
    return bytes(out)


def filesystem(image):
    return bytearray(b''.join(image[c*9*512:(c*9+8)*512] for c in range(40)))


def allocation(fs, name):
    """Locate a user-0 file in this original 160K CP/M filesystem.

    1K allocation blocks, byte block numbers, 16K extents, 64 directory entries.
    This is a deliberately limited original-layout reader, not a general writer.
    """
    stem, ext = name.upper().split('.')
    key = (stem.ljust(8)+ext.ljust(3)).encode('ascii')
    extents = []
    for at in range(4096, 4096+2048, 32):
        entry = fs[at:at+32]
        if entry[0] or bytes(x & 127 for x in entry[1:12]) != key:
            continue
        index = (entry[12] & 31) + 32*(entry[14] & 63)
        remaining = entry[15]*128
        locations = []
        for block in entry[16:32]:
            if not remaining:
                break
            if block < 2 or block > 155:
                raise ValueError('invalid allocation block')
            size = min(1024, remaining)
            locations.append((4096+block*1024, size))
            remaining -= size
        if remaining:
            raise ValueError('truncated extent')
        extents.append((index, locations))
    extents.sort()
    if [e[0] for e in extents] != list(range(len(extents))) or not extents:
        raise ValueError(f'missing / noncontiguous extents: {name}')
    return [location for _, locations in extents for location in locations]


def add_file(fs, name, content, first_block, first_entry, protected=False):
    """Allocate user-0 extents contiguously on this one 160K CP/M format."""
    stem, extension = name.upper().split('.')
    if not 1 <= len(stem) <= 8 or not 1 <= len(extension) <= 3:
        raise ValueError('not an 8.3 filename')
    key=(stem.ljust(8)+extension.ljust(3)).encode('ascii')
    padded_content=content+b'\x1a'*((-len(content))%128)
    position=0
    block=first_block
    entry_index=first_entry
    extent=0
    while position < len(padded_content):
        size=min(16384,len(padded_content)-position)
        count=(size+1023)//1024
        if entry_index >= 64 or block < 2 or block+count > 156:
            raise ValueError('disk capacity exceeded')
        entry=bytearray(32)
        entry[1:12]=key
        if protected:
            # Original SPEED.STR and LOGO.STM both carry R/O and SYS flags.
            entry[9] |= 0x80
            entry[10] |= 0x80
        entry[12]=extent & 31
        entry[14]=extent >> 5
        entry[15]=size//128
        entry[16:16+count]=bytes(range(block,block+count))
        offset=4096+entry_index*32
        fs[offset:offset+32]=entry
        at=4096+block*1024
        fs[at:at+size]=padded_content[position:position+size]
        position+=size
        block+=count
        entry_index+=1
        extent+=1
    spans=allocation(fs,name)
    if b''.join(fs[a:a+n] for a,n in spans) != padded_content:
        raise ValueError('written file failed allocation round trip')
    return block,entry_index


def build():
    kernel = (ROOT/'kernel/basic.str').read_bytes()
    app = (BASE/'msbasic.cmd').read_bytes()
    if len(app) < 128 or app[0] != 1:
        raise ValueError('application must have CODE as its first CMD group')
    encoded = transform(app, [0xb4, 0xa5])
    if transform(encoded, [0xb4, 0xa5]) != app:
        raise ValueError('application encoding round trip failed')
    write(ROOT/'msbasic.stm', encoded)
    fs = bytearray(b'\xe5' * (320*512))
    block, entry = add_file(fs, 'SPEED.STR', kernel, 2, 0, protected=True)
    if (block, entry) != (18, 1):
        raise ValueError('fixed loader needs the 16K kernel in blocks 2..17')
    add_file(fs, 'MBASIC86.STM', encoded, block, entry, protected=True)
    image = bytearray(b'\xe5' * (360*512))
    for c in range(40):
        image[c*9*512:(c*9+8)*512] = fs[c*8*512:(c+1)*8*512]
    image[:512] = (ROOT/'kernel/basic-boot.bin').read_bytes()
    image[4096:4608] = (ROOT/'kernel/basic-loader.bin').read_bytes()
    if len(image) != 184320:
        raise ValueError('incorrect boot-sector sizes')
    write(ROOT/'stm-basic.img', image)
    # ImageDisk: fixed reproducible header; uncompressed 512-byte sectors.
    imd = bytearray(b'IMD 1.18: SpeedStart MS BASIC\r\n\x1a')
    for c in range(40):
        sectors = 9 if c == 0 else 8
        imd.extend(bytes([5, c, 0, sectors, 2])) # 250 kbps MFM, head 0, size 512
        imd.extend(bytes(range(1, sectors+1)))
        for s in range(sectors):
            imd.append(1) # normal, uncompressed sector
            at = (c*9+s)*512
            imd.extend(image[at:at+512])
    write(ROOT/'stm-basic.imd', imd)
    print('Built stm-basic.img and stm-basic.imd (SPEED.STR + MBASIC86.STM)')


if __name__ == '__main__':
    build()
