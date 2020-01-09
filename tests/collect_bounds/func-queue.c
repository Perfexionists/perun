/** @bench-003-partitioning.c
 *
 * Container: SLL traversal
 * Detail: Terminating SLL traversal with interesting amortized complexity
 * Real Bounds: O(x<next^n>NULL)*2
 * Optimal Complexity: O(x<next^n>NULL)*2
 * Overall Complexity: O(x<next^n>NULL)*O(y<next^n>x)
 */
#include "tebap.h"
#include <stdio.h>
#include <stdlib.h>

typedef struct list_t {
    struct list_t* next;
} TList;

unsigned int k = 10;

int bench_vmcai_bench_008_func_queue(unsigned int k) {
    TList *head, *tail, *temp;

    unsigned int head_next_NULL;
    unsigned int tail_next_NULL;
    tail = NULL;
    head = NULL;
    head_next_NULL = 0;
    tail_next_NULL = 0;

    while (k > 0) {
        if (NONDET) {
            temp = malloc(sizeof(TList));
            temp->next = tail;
            tail = temp;
            head_next_NULL = 0;
            tail_next_NULL += 1;
            tail_next_NULL = 1;
        } else {
            while (head_next_NULL > 0 && head != NULL) {
                temp = head;
                head = head->next;
                free(temp);
                head_next_NULL -= 1;
            }
            head = NULL;
            head_next_NULL = 0;

            while (tail_next_NULL > 0 && tail != NULL) {
                temp = tail->next;
                tail->next = head;
                head = tail;
                tail = temp;
                head_next_NULL += 1;
                tail_next_NULL -= 1;
            }
        }

        --k;
    }

    // Clean up
    while(head != NULL) {
        temp = head;
        head = head->next;
        free(temp);
    }

    while(tail_next_NULL > 0 && tail != NULL) {
        temp = tail;
        tail = tail->next;
        free(temp);
        tail_next_NULL -= 1;
    }

    return 0;
}
