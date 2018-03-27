CC=g++
CFLAGS=-g -std=c++11 -pedantic -Wall -Wextra

TST_SOURCE=workload/

main: $(TST_SOURCE)main.cpp $(TST_SOURCE)SLList.h $(TST_SOURCE)SLListcls.h
	$(CC) $(CFLAGS) -o ../tst $(TST_SOURCE)main.cpp

clean:
	rm -f ../tst *.o 

run:
	./tst
