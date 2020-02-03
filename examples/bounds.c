int partitioning(unsigned int k) {
    TList *list, *temp;

    unsigned int list_next_NULL;
    unsigned int list_next_p;
    unsigned int p_next_NULL;
    unsigned int x_next_NULL;
    unsigned int y_next_x;
    list = malloc(sizeof(TList));
    list->next = NULL;

    // Create nondeterminstic list
    TList *p = list;
    list_next_NULL = 1;
    list_next_p = 0;
    while(k > 1) {
        temp = malloc(sizeof(TList));
        temp->next = NULL;
        p->next = temp;
        p = temp;
        list_next_NULL = list_next_p + 2;
        list_next_p += 1;
        --k;
    }

    // Traverse the list
    TList* x = list;
    TList* y = x;
    x_next_NULL = list_next_NULL;
    y_next_x = 0;
    while(x_next_NULL > 0 && x != NULL) {
        x = x->next;
        x_next_NULL -= 1;
        y_next_x += 1;
        // The end will always jump out
        if(NONDET) {
            while(y_next_x > 0 && y != x) {
                y = y->next;
                y_next_x -= 1;
            }
        }
    }

    p = list;
    p_next_NULL = list_next_NULL;
    while(p_next_NULL > 0 && p != NULL) {
        temp = p;
        p = p->next;
        free(temp);
        p_next_NULL -= 1;
    }

    return 0;
}

