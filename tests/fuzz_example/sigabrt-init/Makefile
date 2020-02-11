CC=gcc
PROG=sigabrt

all: $(PROG)

sigabrt: main.c
	$(CC) $< --coverage -o $@

clean:
	rm -rf $(PROG) *.gc*
