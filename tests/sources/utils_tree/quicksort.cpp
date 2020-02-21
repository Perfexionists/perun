#include "sorts.h"
#include <iostream>

const int MAX_SORT_ARR_LEN = 30;
const int SORT_ARR_LEN_INC = 5;


int main() {

    // Run bad quicksort on different scales with reverse sorted input
    for(int i = SORT_ARR_LEN_INC; i <= MAX_SORT_ARR_LEN; i += SORT_ARR_LEN_INC) {
        int *input = new int[i];

        for(int j = 0; j < i; j++) {
            input[j] = i - j - 1;
        }

        QuickSortBad(input, i);
        delete[] input;
    }

    return 0;
}
