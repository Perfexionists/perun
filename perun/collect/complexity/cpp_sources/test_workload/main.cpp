#include "SLList.h"
#include "SLListcls.h"
#include "../profile_api.h"

int main() {

    SLList mylist;
    _profapi_register_size_address(&mylist, false, &mylist.size);
    SLList_init(&mylist);
    for(int i = 0; i < 10; i++) {
        _profapi_using_size_address(&mylist);
        SLList_insert(&mylist, i + 1);
    }
    _profapi_using_size_address(&mylist);
    SLList_search(&mylist, 3);
    _profapi_using_size_address(&mylist);
    SLList_destroy(&mylist);

    SLListcls clslist;
    for(int i = 0; i < 10; i++) {
        clslist.Insert(i + 1);
    }
    clslist.Search(3);



    return 0;
}
