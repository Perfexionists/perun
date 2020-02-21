#ifndef PROTOTYPE_PROFILE_API_H
#define PROTOTYPE_PROFILE_API_H

#include <cstddef>

/*
 * First prototype version of profiling API, subject to change
 */

// Allows the structure to register itself for the size profiling by providing it's size address
// Provides two modes of registration - injected and outer.
//
// In case of injected registration, all subsequent profiling api functions should be
// called from within the structure methods which are profiled.
//
// In case of outer registration, all subsequent api calls should annotate the profiled
// method calls.
// ----------------------------------------------------------------
// Arguments:
//  -- struct_addr: address of the structure instance to profile
//  -- is_injected: specifies the registration mode
//  -- struct_size_address: the address of the variable that holds the structure size
// Returns:
//  -- void
// Throws:
//  -- None
void __attribute__((no_instrument_function)) _profapi_register_size_address(void *struct_addr, bool is_injected,
                                                                            size_t *struct_size_address);

// Allows the structure to register itself for the size profiling by providing it's size value
// Provides two modes of registration - injected and outer.
//
// In case of injected registration, all subsequent profiling api functions should be
// called from within the structure methods which are profiled.
//
// In case of outer registration, all subsequent api calls should annotate the profiled
// method calls.
// ----------------------------------------------------------------
// Arguments:
//  -- struct_addr: address of the structure instance to profile
//  -- is_injected: specifies the registration mode
//  -- struct_size_value: the current structure size as a value
// Returns:
//  -- void
// Throws:
//  -- None
void __attribute__((no_instrument_function)) _profapi_register_size_value(void *struct_addr, bool is_injected,
                                                                          size_t struct_size_value);

// Allows the structure to unregister itself from the size profiling. Even though this is
// optional operation, it is advised to perform this cleanup at least for structures that
// registered the size address. If any api subsequent api call is made for structure that
// no longer exists, there is high risk of accessing invalid memory pointer, thus causing
// program failure. In contrary, trying to access non registered / unregistered is
// evaluated simply as an empty operation.
// ----------------------------------------------------------------
// Arguments:
//  -- struct_addr: address of the structure instance to be unregistered from the profiling
// Returns:
//  -- void
// Throws:
//  -- None
void __attribute__((no_instrument_function)) _profapi_unregister_size(void *struct_addr);

// Marks the function as a size profiling target. If the data structure was registered as
// a injected one, this call should happen somewhere inside the called function, otherwise
// should be called right before the profiled function call. This allows the profiling lib
// to track the structure size for various structure operations.
//
// This specific function should be called if a size variable address was registered.
// ----------------------------------------------------------------
// Arguments:
//  -- struct_addr: address of the structure instance to be unregistered from the profiling
// Returns:
//  -- void
// Throws:
//  -- None
void __attribute__((no_instrument_function)) _profapi_using_size_address(void *struct_addr);

// Marks the function as a size profiling target. If the data structure was registered as
// a injected one, this call should happen somewhere inside the called function, otherwise
// should be called right before the profiled function call. This allows the profiling lib
// to track the structure size for various structure operations.
//
// This specific function should be called if a size variable value was registered.
// This function also updates the actual structure size by passing it as a parameter.
// ----------------------------------------------------------------
// Arguments:
//  -- struct_addr: address of the structure instance to be unregistered from the profiling
//  -- size_value: the actual structure size value
// Returns:
//  -- void
// Throws:
//  -- None
void __attribute__((no_instrument_function)) _profapi_using_size_value(void *struct_addr, size_t size_value);

// Provides the structure size to the profiling functions based on a stack frame address.
// If the stack frame address matches the last obtained size record, this size record is
// provided. Mainly used for the __cyg* profiling functions and thus provides very limited
// general use.
// ----------------------------------------------------------------
// Arguments:
//  -- stack_frame: the address of the stack frame which is used for size record searching
// Returns:
//  -- size_t: the recorded structure size or 0 if not found or unknown size
// Throws:
//  -- None
size_t __attribute__((no_instrument_function)) _profapi_get_size_record(void *stack_frame);

// Removes the top size record if it's frame address matches the stack frame in argument.
// ----------------------------------------------------------------
// Arguments:
//  -- stack_frame: the address of the stack frame which is used for size record searching
// Returns:
//  -- void
// Throws:
//  -- None
void __attribute__((no_instrument_function)) _profapi_remove_size_record(void *stack_frame);

// Removes sequence of records where the frame address is the same or lower than the one
// provided as a argument. May be used to clean the records, which were not used.
// ----------------------------------------------------------------
// Arguments:
//  -- stack_frame: the address of the stack frame which is used for size record searching
// Returns:
//  -- void
// Throws:
//  -- None
void __attribute__((no_instrument_function)) _profapi_clean_size_records(void *stack_frame);

#endif //PROTOTYPE_PROFILE_API_H
