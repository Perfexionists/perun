CC=gcc
PROG=hang

all: $(PROG)

hang: main.c
	$(CC) $< -g --coverage -o $@

clean:
	rm -rf $(PROG) *.gc*
