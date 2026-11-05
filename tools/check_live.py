"""Boot SpeedStart BASIC and verify arithmetic plus disk SAVE/NEW/LOAD/RUN."""
import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
CFG = '''path = "{rom}"
system {{ model="5160" boot=0 rtc=1 memtest=0 floppy_disk_drives=1
 patch_bios_init=1 patch_bios_int19=1 }}
cpu {{ model="8088" speed=8 }}
ram {{ address=0 size=640K }}
rom {{ address=0xf0000 size=64K }}
load {{ format="binary" address=0xfe000 file="ibm-xt-1982-11-08.rom" }}
load {{ format="binary" address=0xf6000 file="ibm-basic-1.10.rom" }}
load {{ format="binary" address=0xf0000 file="ibmpc-pcex.rom" }}
terminal {{ driver="null" escape="F12" }}
video {{ device="cga" font=1 blink=30 }}
fdc {{ address=0x3f0 irq=6 drive0=0 accurate=0 ignore_eot=1 }}
disk {{ drive=0 type="auto" file="disk.imd" optional=0 }}
'''

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from image import payloads,padded,filesystem,allocation
KEYS={' ':'Space','*':'+Shift 8 -Shift','+':'+Shift Equal -Shift',
      '"':'+Shift Apostrophe -Shift'}


def screen(data):
    return '\n'.join(data[i:i+160:2].decode('cp437').rstrip() for i in range(0,4000,160))


def run(rom):
    with tempfile.TemporaryDirectory(prefix='stm-basic-') as temp:
        folder=Path(temp)
        shutil.copyfile(ROOT/'stm-basic.imd',folder/'disk.imd')
        (folder/'cfg').write_text(CFG.format(rom=rom))
        script=['c f000000','save "start.bin" bin b800:0000 fa0']

        def command(text):
            for char in text:
                script.extend(['key '+KEYS.get(char,char),'c 200000'])
            script.extend(['key Return','c 5000000'])

        command('print 6*7')
        script.append('save "arithmetic.bin" bin b800:0000 fa0')
        for text in ('10 print 12345+67890','save "proof"','new','load "proof"','run'):
            command(text)
        script.extend(['save "loaded.bin" bin b800:0000 fa0','q'])
        result=subprocess.run(['pce-ibmpc','-c','cfg','-t','null','-g','cga'],cwd=folder,
                              input=('\n'.join(script)+'\n').encode(),capture_output=True,
                              timeout=180)
        if result.returncode or b'unknown key:' in result.stdout+result.stderr:
            raise RuntimeError((result.stdout+result.stderr).decode(errors='replace')[-2500:])
        frames={n:screen((folder/(n+'.bin')).read_bytes()) for n in ('start','arithmetic','loaded')}
        if 'Microsoft BASIC Version 5.50A' not in frames['start']:
            raise AssertionError('BASIC did not boot:\n'+frames['start'])
        if '42' not in [line.strip() for line in frames['arithmetic'].splitlines()]:
            raise AssertionError('arithmetic failed:\n'+frames['arithmetic'])
        if '80235' not in [line.strip() for line in frames['loaded'].splitlines()]:
            raise AssertionError('SAVE/NEW/LOAD/RUN failed:\n'+frames['loaded'])
        fs=filesystem(padded(payloads(folder/'disk.imd')))
        spans=allocation(fs,'PROOF.BAS')
        saved=b''.join(fs[a:a+n] for a,n in spans)
        if not saved or all(x in (0,26,229) for x in saved):
            raise AssertionError('saved BASIC program is empty')
    print('PASS: self-booting BASIC 5.50A; 6*7=42; disk SAVE/NEW/LOAD/RUN produces 80235')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom-dir',type=Path,required=True)
    run(p.parse_args().rom_dir.resolve())
