# core firmware: PIC32MK1024MCM064, MPLAB XC32 (v5.00) + PIC32MK-MC_DFP.
#   make            build build/core.hex and print the memory summary
#   make clean
XC32    ?= $(HOME)/microchip/xc32/v5.00/bin
DFP     ?= $(HOME)/microchip/packs/Microchip/PIC32MK-MC_DFP/1.13.270
CPU     := 32MK1024MCM064
CFLAGS  := -mprocessor=$(CPU) -mdfp=$(DFP) -O1 -std=gnu99 -Wall -Wextra -Wno-unused-parameter -ffunction-sections
LDFLAGS := -mprocessor=$(CPU) -mdfp=$(DFP) -Wl,--gc-sections,--report-mem,-Map=build/core.map
SRC     := $(wildcard src/*.c)
OBJ     := $(SRC:src/%.c=build/%.o)
OUT     := build/core

$(OUT).hex: $(OUT).elf
	$(XC32)/xc32-bin2hex $<

$(OUT).elf: $(OBJ)
	$(XC32)/xc32-gcc $(LDFLAGS) -o $@ $^

build/%.o: src/%.c $(wildcard src/*.h) Makefile
	@mkdir -p build
	$(XC32)/xc32-gcc $(CFLAGS) -c -o $@ $<

clean:
	rm -rf build

.PHONY: clean
