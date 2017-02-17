#include "SLList.h"
#include "SLListcls.h"

int main() {
    SLList mylist;
    SLList_init(&mylist);
    SLList_insert(&mylist, 1);
    for(int i = 0; i < 1000; i++) {
        SLList_insert(&mylist, i + 1);
    }
    SLList_search(&mylist, 3);
    SLList_search(&mylist, 997);
    SLList_destroy(&mylist);

    SLListcls clslist;
    for(int i = 0; i < 1000; i++) {
        clslist.Insert(i + 1);
    }
    clslist.Search(3);
    clslist.Search(997);

    return 0;
}
