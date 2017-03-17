/*
 * File:        test.cpp
 * Project:     Library for Profiling and Visualization of Memory Consumption
 *              of C/C++ Programs, Bachelor's thesis
 * Date:        29.2.2017
 * Author:      Podola Radim, xpodol06@stud.fit.vutbr.cz
 * Description: Testing file for injected malloc.so library.

TODO: Test for all allocation functions, use assert?
 */

#include <iostream>     // std::cout
#include <new>          // ::operator new

struct MyClass {
  int data[100];
  MyClass(){(int*)calloc(1, sizeof(int));	}
};

int main () {

  MyClass* p1 = new MyClass();
      // allocates memory by calling: operator new (sizeof(MyClass))
      // and then constructs an object at the newly allocated space

  int *i = new int;
  delete(i);
  delete(p1);

  return 0;
}
