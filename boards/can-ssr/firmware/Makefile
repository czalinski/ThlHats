# can-ssr firmware: PIC18F47Q84, MPLAB XC8 (v4.00 tested).
#   make            build build/can-ssr.hex and print the memory summary
#   make clean
XC8     ?= $(HOME)/microchip/xc8/v4.00/bin/xc8-cc
DFP     ?= $(HOME)/microchip/packs/Microchip/PIC18F-Q_DFP/1.31.492/xc8
CPU     := 18F47Q84
CFLAGS  := -mcpu=$(CPU) -mdfp=$(DFP) -O2 -std=c99 -Wall -msummary=-psect,-class,+mem,-hex,-file
SRC     := $(wildcard src/*.c)
OUT     := build/can-ssr

$(OUT).hex: $(SRC) $(wildcard src/*.h) Makefile
	@mkdir -p build
	$(XC8) $(CFLAGS) -o $(OUT).elf $(SRC)

clean:
	rm -rf build

.PHONY: clean
