CC=gcc
PROG=hang

all: $(PROG)

hang: main.c
	$(CC) $< --coverage -o $@

clean:
	rm -rf $(PROG) *.gc*
