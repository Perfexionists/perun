CC=gcc
PROG=hang

all: $(PROG)

hang: hang.c
	$(CC) $< -g --coverage -o $@

clean:
	rm -rf $(PROG) *.gc*
