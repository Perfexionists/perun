#ifndef PROTOTYPE_PROFILE_API_H
#define PROTOTYPE_PROFILE_API_H

#include <cstddef>

/*
 * First prototype version of API, subject to change
 */

void __attribute__((no_instrument_function)) Register_size_address(void *struct_addr, bool is_injected, size_t *struct_size_address);

void __attribute__((no_instrument_function)) Register_size_value(void *struct_addr, bool is_injected, size_t struct_size_value);

void __attribute__((no_instrument_function)) Unregister_size(void *struct_addr);

void __attribute__((no_instrument_function)) Using_size_address(void *struct_addr);

void __attribute__((no_instrument_function)) Using_size_value(void *struct_addr, size_t size_value);

std::size_t __attribute__((no_instrument_function)) Get_size_record(void *stack_frame);

#endif //PROTOTYPE_PROFILE_API_H
