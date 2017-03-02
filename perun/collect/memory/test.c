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

int factorial(unsigned int i) {

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

	int *n;
	n = (int*)malloc(sizeof(int));	

	*n = 5;
	printf("%i\n", *n);

	free(n);

	for (int i = 0; i < 5; ++i){

		foo1(i);
	}
	factorial(5);

	return 0;
}