PYTHON ?= python3
ROM_DIR ?= $(HOME)/.local.darwin/emulators/share/pce/ibmpc

.PHONY: all kernel check check-live run clean stm-basic.img stm-basic.imd
all: kernel
	$(PYTHON) -B tools/image.py

kernel:
	$(MAKE) -C kernel

stm-basic.img stm-basic.imd: all

check: all
	$(MAKE) -C kernel check
	$(PYTHON) -B tools/check.py

check-live: check
	$(PYTHON) -B tools/check_live.py --rom-dir "$(ROM_DIR)"

run: all
	./stm

clean:
	$(MAKE) -C kernel clean
	rm -f stm-basic.img stm-basic.imd msbasic.stm
