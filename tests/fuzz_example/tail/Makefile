#  Makefile
#  Riešenie IJC-DU1,  23.4.2017
#  Autor: Matúš Liščinský, FIT
#  Login: xlisci02
#  GCC: gcc 5.4.0 (merlin)
#  make - preklad
#  make clean - vymazanie suborov do stavu ako pred prekladom

# compilers & flags
CC=gcc
CppC=g++
CFLAGS=-g -std=c99 -pedantic -Wall -Wextra --coverage
CppFLAGS=-g -std=c++11 -pedantic -Wall --coverage

#all
PROGRAMS=tail 

all: $(PROGRAMS)

# bin. subory
tail: tail.o 
	$(CC) $(CFLAGS) tail.o -o tail

tail.o: tail.c
	$(CC) $(CFLAGS) -c tail.c -o tail.o

# cistenie do stavu ako pred zostavenim 
clean:
	rm -rf *.o $(PROGRAMS) *.gc*
