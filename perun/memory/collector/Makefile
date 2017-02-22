#
# Soubor:		Makefile
# Datum:		10.2.2017
# Autor:		Podola Radim, 	xpodol06@stud.fit.vutbr.cz
# Překladač:	gcc 5.4.0
# Popis:		Soubor obsahuje popis překladu zdrojových souborů
#				pro aplikaci make.
#

all: test test++

test: test.c
	gcc -g -std=c99 -Wextra -pedantic -Wall test.c -o test

test++: t.cpp
	g++ -g -std=c++11 -Wextra -pedantic -Wall t.cpp -o test++


lib: malloc.c backtrace.c
	gcc -O0 -shared -fPIC malloc.c backtrace.c -o malloc.so -lunwind -ldl


profile:
	LD_PRELOAD="$$PWD/malloc.so" ./test

profile++:
	LD_PRELOAD="$$PWD/malloc.so" ./test++

clean-logs:
	rm MemoryLog

clean:
	rm -f test++ test MemoryLog

zip:
	tar -cvf xpodol06.tar $(ZIPFILES)
