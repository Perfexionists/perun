#include "SLList.h"
#include "SLListcls.h"
#include "../profile_api.h"

int main() {

    SLList mylist;
    Register_size_address(&mylist, false, &mylist.size);
    SLList_init(&mylist);
    for(int i = 0; i < 10; i++) {
        Using_size_address(&mylist);
        SLList_insert(&mylist, i + 1);
    }
    Using_size_address(&mylist);
    SLList_search(&mylist, 3);
    Using_size_address(&mylist);
    SLList_destroy(&mylist);

    SLListcls clslist;
    for(int i = 0; i < 10; i++) {
        clslist.Insert(i + 1);
    }
    clslist.Search(3);



    return 0;
}
