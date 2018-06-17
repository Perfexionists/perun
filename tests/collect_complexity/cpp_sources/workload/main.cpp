#include "SLList.h"
#include "SLListcls.h"

int main() {

    SLList mylist;
    SLList_init(&mylist);
    for(int i = 0; i < 10; i++) {
        SLList_insert(&mylist, i + 1);
    }
    SLList_search(&mylist, 3);
    SLList_destroy(&mylist);

    SLListcls clslist;
    for(int i = 0; i < 10; i++) {
        clslist.Insert(i + 1);
    }
    clslist.Search(3);

    return 0;
}
