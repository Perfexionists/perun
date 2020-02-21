CC=g++
CFLAGS=-g -std=c++11 -pedantic -Wall -Wextra

main: tst.cpp tst_waiting.cpp sorts.h
	$(CC) $(CFLAGS) -o ../tst tst.cpp
	$(CC) $(CLFAGS) -o ../tst_waiting tst_waiting.cpp

clean:
	rm -f ../tst ../tst_waiting *.o

run:
	../tst
