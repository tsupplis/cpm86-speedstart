ASM86 ?= cpm86_asm86
PYTHON ?= python3
SOURCES = boot.a86 loader.a86 header.a86 ccp.a86 bdos.a86 bios.a86 basboot.a86 basload.a86 basccp.a86
HEX = $(SOURCES:.a86=.h86)

.PHONY: all check clean
.DELETE_ON_ERROR:
all: $(HEX)
	$(PYTHON) -B ../tools/kernel.py

%.h86: %.a86
	$(ASM86) $<

check: all
	cmp boot.bin ../base/boot-sector.bin
	cmp loader.bin ../base/track0-sector9.bin
	cmp speed.str ../base/speed.str

clean:
	rm -f *.h86 *.lst *.sym *.bin *.dec *.str
