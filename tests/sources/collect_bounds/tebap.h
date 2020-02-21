#ifndef __TEBAP_H__
#define __TEBAP_H__

//    Constants definition
#define CLOOPUS
#define FIXED_SIZE 10
#ifndef CLOOPUS
#define COMPILE_FOR_FORESTER
#endif

//    Headers specific for Forester/Loopus
#ifdef COMPILE_FOR_FORESTER
#include <verifier-builtins.h>
#endif

//    Definition of nondet() function for both of the tools
// [TODO] This is not exactly clean, think of better way
#ifdef COMPILE_FOR_FORESTER
//    Forester is using the __VERIFIER_nondet_int() func for modeling
//  of the nondeterminism 
#define NONDET __VERIFIER_nondet_int()
#else
//    Loopus is using the global variable and two function in order to
//  hack the compiler into thinking considering that the function can
//  return anything
int nondetnonarg;

int nondetnon2(int arg) {
    nondetnonarg = nondetnon2(nondetnonarg);
    return nondetnonarg;
}

int nondetnon() {
    nondetnonarg = nondetnon2(nondetnonarg);
    return nondetnonarg;
}

#define NONDET nondetnon()

int __VERIFIER_plot(char * s) { return 0;
}
#endif

#endif
