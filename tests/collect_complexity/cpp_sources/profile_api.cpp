#include <unordered_map>
#include <vector>
#include "profile_api.h"

/*
 * First prototype version of API, subject to change
 */

// The record structure for registered structures and their sizes
// Only address or value is used in one record, which depends on the registered type
struct Struct_size_details {
    // Constructors
    Struct_size_details() : size_address{nullptr}, size_value{0}, is_injected{false} {}

    Struct_size_details(bool is_injected, size_t* size_address) :
            size_address{size_address}, size_value{0}, is_injected{is_injected} {}

    Struct_size_details(bool is_injected, size_t size_value) :
            size_address{nullptr}, size_value{size_value}, is_injected{is_injected} {}

    size_t *size_address;       // The address of a structure size variable
    size_t size_value;          // The last known value of a structure size variable
    bool is_injected;           // Specifies if the functions are injected in the struct operations
};

// The record structure for the size stack
struct Size_stack_record {
    // Constructor
    Size_stack_record(void *frame, size_t size) :
            stack_frame{frame}, actual_size{size} {}

    void *stack_frame;          // The stack frame address from when the record was made
    size_t actual_size;         // The actual struct size value at that time
};

// The structure objects : details mapping, holds info about the registered structures
static std::unordered_map<void *, Struct_size_details> struct_size_map;
// The size stack used for size records capture
static std::vector<Size_stack_record> size_stack;


void _profapi_register_size_address(void *struct_addr, bool is_injected, size_t *struct_size_address) {
    // Insert new structure object mapping with size address
    struct_size_map[struct_addr] = Struct_size_details(is_injected, struct_size_address);
}

void _profapi_register_size_value(void *struct_addr, bool is_injected, size_t struct_size_value) {
    // Insert new structure object mapping with size value
    struct_size_map[struct_addr] = Struct_size_details(is_injected, struct_size_value);
}

void _profapi_unregister_size(void *struct_addr) {
    // Removes mapped structure from the map
    struct_size_map.erase(struct_addr);
}

void _profapi_using_size_address(void *struct_addr) {
    // Try to find the object mapping
    auto struct_record = struct_size_map.find(struct_addr);
    if(struct_record != struct_size_map.end()) {
        // If the profiling is injected, use the upper stack frame to match the upcoming searching
        if(struct_record->second.is_injected) {
            size_stack.push_back(Size_stack_record(__builtin_frame_address(1), *(struct_record->second.size_address)));
        } else {
            size_stack.push_back(Size_stack_record(__builtin_frame_address(0), *struct_record->second.size_address));
        }
    }
}

void _profapi_using_size_value(void *struct_addr, size_t size_value) {
    // Try to find the object mapping and update the structure size
    auto struct_record = struct_size_map.find(struct_addr);
    if(struct_record != struct_size_map.end()) {
        struct_record->second.size_value = size_value;
        // If the profiling is injected, use the upper stack frame to match the upcoming searching
        if (struct_record->second.is_injected) {
            size_stack.push_back(Size_stack_record(__builtin_frame_address(1), struct_record->second.size_value));
        } else {
            size_stack.push_back(Size_stack_record(__builtin_frame_address(0), struct_record->second.size_value));
        }
    }
}

size_t _profapi_get_size_record(void *stack_frame) {
    // Check if the top stack frame and provided frame match
    if(!size_stack.empty() && stack_frame == size_stack.back().stack_frame) {
        size_t struct_size = size_stack.back().actual_size;
        size_stack.pop_back();
        return struct_size;
    } else {
        return 0;
    }
}

void _profapi_remove_size_record(void *stack_frame) {
    // Check if the stack contains such record
    if(!size_stack.empty() && stack_frame == size_stack.back().stack_frame) {
        size_stack.pop_back();
    }
}

void _profapi_clean_size_records(void *stack_frame) {
    // Clean all the records that were not used (i.e. with same or lower stack address)
    while(!size_stack.empty() && stack_frame >= size_stack.back().stack_frame) {
        size_stack.pop_back();
    }
}
