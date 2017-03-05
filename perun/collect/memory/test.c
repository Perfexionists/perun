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

int factorial(unsigned int i){

   if(i <= 1) {
      return 1;
   }
   
	free(malloc(sizeof(int)));

	return i * factorial(i - 1);
}

void foo2(){

	int *n;
	n = (int*)calloc(1, sizeof(int));	
}

void foo1(int k){

	free(malloc(sizeof(int)*k));
	foo2();
}


int main(){

	int *n, *m, res;

	n = (int*)malloc(sizeof(int));
	*n = 5;
	assert(*n == 5);

	m = (int*)realloc(n, sizeof(int)*5);
	assert(*m == 5);

	free(m);
	n = NULL;

	n = (int*)calloc(5, sizeof(int));
	assert(*n == 0);
	free(n);

	n = (int*)memalign(8, sizeof(int));
	assert((int)n % 8 == 0);
	free(n);

	res = posix_memalign(&n, 8, sizeof(int));
	assert(((int)n % sizeof(void *)) == 0);
	assert(res == 0);

	n = (int*)valloc(sizeof(int));
	assert((int)n % sysconf(_SC_PAGESIZE) == 0);
	free(n);

	for(int i = 0; i < 5; ++i){
		foo1(i);
	}

	factorial(5);

	return 0;
}