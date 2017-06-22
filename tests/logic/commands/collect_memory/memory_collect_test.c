/*
 * File:        test.c
 * Project:     Library for Profiling and Visualization of Memory Consumption
 *              of C/C++ Programs, Bachelor's thesis
 * Date:        29.2.2017
 * Author:      Podola Radim, xpodol06@stud.fit.vutbr.cz
 * Description: Testing file for injected malloc.so library.

TODO: Test for all allocation functions, use assert?
 */
#include <stdio.h>
#include <stdlib.h>
#include <malloc.h>
#include <assert.h>
#include <unistd.h>

void fun() {
    int *n;
    n = malloc(sizeof(int));
    free(n);
}


int main(){

	int *n, *m, res;

	n = (int*)malloc(sizeof(int));
	*n = 5;
	free(n);

	return 0;
}
