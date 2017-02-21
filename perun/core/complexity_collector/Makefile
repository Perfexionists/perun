CC=g++
CFLAGS=-g -std=c++11 -pedantic -Wall -Wextra
CINSTR=-finstrument-functions
#-finstrument-functions-exclude-file-list=stl_construct.h
#-finstrument-functions-exclude-function-list=vector
#-finstrument-functions-exclude-function-list=__static_initialization_and_destruction_0,_GLOBAL__sub_I__Z11SLList_initP6SLList

profile: main.o profile.o config.o
	$(CC) -o profile main.o profile.o config.o

profile.o: config.o profile.cpp
	$(CC) $(CFLAGS) -c -o profile.o profile.cpp

config.o: Configuration.cpp Configuration.h
	$(CC) $(CFLAGS) -c -o config.o Configuration.cpp

main.o: main.cpp SLList.h SLListcls.h
	$(CC) $(CFLAGS) $(CINSTR) -c -o main.o main.cpp

clean:
	rm -f profile.o main.o config.o profile trace.out 

run:
	./profile
	gedit trace.log
