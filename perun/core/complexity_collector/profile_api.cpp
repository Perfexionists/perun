#include <unordered_map>
#include <vector>
#include "profile_api.h"

/*
 * First prototype version of API, subject to change
 */

struct Size_stack_record {
    Size_stack_record(void *frame, size_t size) :
            stack_frame{frame}, actual_size{size} {}

    void *stack_frame;
    size_t actual_size;
};

struct Struct_size_details {
    Struct_size_details() : size_address{nullptr}, size_value{0}, is_injected{false} {}

    Struct_size_details(bool is_injected, size_t* size_address) :
            size_address{size_address}, size_value{0}, is_injected{is_injected} {}

    Struct_size_details(bool is_injected, size_t size_value) :
            size_address{nullptr}, size_value{size_value}, is_injected{is_injected} {}

    size_t *size_address;
    size_t size_value;
    bool is_injected;
};

std::unordered_map<void *, Struct_size_details> struct_size_map;
std::vector<Size_stack_record> size_stack;


void Register_size_address(void *struct_addr, bool is_injected, size_t *struct_size_address) {
    struct_size_map[struct_addr] = Struct_size_details(is_injected, struct_size_address);
}

void Register_size_value(void *struct_addr, bool is_injected, size_t struct_size_value) {
    struct_size_map[struct_addr] = Struct_size_details(is_injected, struct_size_value);
}

void Unregister_size(void *struct_addr) {
    struct_size_map.erase(struct_addr);
}

void Using_size_address(void *struct_addr) {
    if(struct_size_map[struct_addr].is_injected) {
        size_stack.push_back(Size_stack_record(__builtin_frame_address(1), *(struct_size_map[struct_addr].size_address)));
    } else {
        size_stack.push_back(Size_stack_record(__builtin_frame_address(0), *struct_size_map[struct_addr].size_address));
    }
}

void Using_size_value(void *struct_addr, size_t size_value) {
    struct_size_map[struct_addr].size_value = size_value;
    if(struct_size_map[struct_addr].is_injected) {
        size_stack.push_back(Size_stack_record(__builtin_frame_address(1), struct_size_map[struct_addr].size_value));
    } else {
        size_stack.push_back(Size_stack_record(__builtin_frame_address(0), struct_size_map[struct_addr].size_value));
    }
}

std::size_t Get_size_record(void *stack_frame) {
    if(!size_stack.empty() && stack_frame == size_stack.back().stack_frame) {
        size_t struct_size = size_stack.back().actual_size;
        size_stack.pop_back();
        return struct_size;
    } else {
        return 0;
    }
}