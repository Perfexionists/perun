CC=gcc
PROG=hang

all: $(PROG)

hang: main.c
	$(CC) $< -g --coverage -dumpbase '' -o $@

clean:
	rm -rf $(PROG) *.gc*
