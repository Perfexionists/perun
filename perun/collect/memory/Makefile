#
# File:		Makefile
# Project:	Library for Profiling and Visualization of Memory Consumption
#               of C/C++ Programs, Bachelor's thesis
# Date:		29.2.2017
# Author:	Podola Radim, xpodol06@stud.fit.vutbr.cz
# Description:	The file contains a description of the source file compilation
# 				for MAKE utility.
#
CC = gcc
.PHONY: clean

all: lib

lib: malloc.c backtrace.c
	$(CC) -shared -fPIC malloc.c backtrace.c -o malloc.so -lunwind -ldl

clean:
	rm -f malloc.so