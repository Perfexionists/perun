/*
 * File:        test.c
 * Project:     Library for Profiling and Visualization of Memory Consumption
 *              of C/C++ Programs, Bachelor's thesis
 * Date:        29.2.2017
 * Author:      Podola Radim, xpodol06@stud.fit.vutbr.cz
 * Description: Testing file for injected malloc.so library.

 */
#include <stdio.h>
#include <stdlib.h>
#include <stdlib.h>
#include <assert.h>
#include <unistd.h>

void fun() {
    int *n;
    n = malloc(sizeof(int));
    free(n);
}


int main(int argc, char** argv){

	int *n, *m, res;

	int repeats = 1;
	if (argc == 2) {
        repeats = atoi(argv[1]);
	}

	n = (int*)malloc(sizeof(int));
	*n = 5;
	free(n);

    while(repeats--) {
        for (int i = 0; i < 1000000; ++i);
        fun();
	}

	m = (int*)malloc(sizeof(int));
	*m = 5;
	free(m);

	return 0;
}
