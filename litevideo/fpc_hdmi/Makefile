# Point to a suitable monospaced TTF font: DejaVu Sans Mono will work, see:
#     https://dejavu-fonts.github.io/
FONT=$(shell fc-match -f %{file} mono)

all: font.hex char0.hex attr0.hex char1.hex attr1.hex

font.hex: font $(FONT)
	./font $(FONT) > $@

font: font.c
	$(CC) $(CFLAGS) $(CPPFLAGS) -o $@ $< $(shell pkg-config --cflags --libs freetype2)

char0.hex attr0.hex char1.hex attr1.hex: char
	./char

char: char.c

.PHONY: all
