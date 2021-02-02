CC=gcc
PROG=sigabrt

all: $(PROG)

sigabrt: main.c
	$(CC) $< -g --coverage -o $@

clean:
	rm -rf $(PROG) *.gc*
