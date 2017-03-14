#
# File:			Makefile
# Project:		Library for Profiling and Visualization of Memory Consumption
#               of C/C++ Programs, Bachelor's thesis
# Date:			29.2.2017
# Author:		Podola Radim, xpodol06@stud.fit.vutbr.cz
# Description:	Soubor obsahuje popis překladu zdrojových souborů
#				pro aplikaci make.
#

all: test test++

test: test.c
	gcc -g -std=c99 -Wextra -pedantic -Wall test.c -o test

test++: test.cpp
	g++ -g -std=c++11 -Wextra -pedantic -Wall test.cpp -o test++


lib: malloc.c backtrace.c
	gcc -shared -fPIC malloc.c backtrace.c -o malloc.so -lunwind -ldl


profile:
	LD_PRELOAD="$$PWD/malloc.so" ./test

profile++:
	LD_PRELOAD="$$PWD/malloc.so" ./test++

clean-logs:
	rm MemoryLog

clean:
	rm -f test++ test MemoryLog

zip:
	zip xpodol06.zip $(ZIPFILES)
