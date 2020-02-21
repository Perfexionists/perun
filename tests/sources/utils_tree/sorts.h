void QuickSort(int *data, int count);
void QuickSortBad(int *data, int count);
void Swap(int& a, int &b);
int Partition(int* data, int left, int right);
int BadPartition(int* data, int left, int right);
void InsertSort(int arr[], int len);
void HeapSort(int array[], int size);
void repairTop(int array[], int bottom, int topIndex);
void swap(int array[], int left, int right);


void QuickSort(int *data, int count) {
    int startIndex = 0;
    int endIndex = count - 1;
    int top = -1;
    int* stack = new int[count];

    stack[++top] = startIndex;
    stack[++top] = endIndex;

    while (top >= 0)
    {
        endIndex = stack[top--];
        startIndex = stack[top--];

        int p = Partition(data, startIndex, endIndex);

        if (p - 1 > startIndex)
        {
            stack[++top] = startIndex;
            stack[++top] = p - 1;
        }

        if (p + 1 < endIndex)
        {
            stack[++top] = p + 1;
            stack[++top] = endIndex;
        }
    }

    delete[] stack;
}

void QuickSortBad(int *data, int count) {
    int startIndex = 0;
    int endIndex = count - 1;
    int top = -1;
    int* stack = new int[count];

    stack[++top] = startIndex;
    stack[++top] = endIndex;

    while (top >= 0)
    {
        endIndex = stack[top--];
        startIndex = stack[top--];

        int p = BadPartition(data, startIndex, endIndex);

        if (p - 1 > startIndex)
        {
            stack[++top] = startIndex;
            stack[++top] = p - 1;
        }

        if (p + 1 < endIndex)
        {
            stack[++top] = p + 1;
            stack[++top] = endIndex;
        }
    }

    delete[] stack;
}


void Swap(int& a, int &b) {
    int temp = a;
    a = b;
    b = temp;
}


int Partition(int* data, int left, int right) {
    int pivot_idx = (left + right) / 2;
    Swap(data[pivot_idx], data[right]);

    int i = (left - 1);

    for (int j = left; j <= right - 1; ++j)
    {
        if (data[j] <= data[right])
        {
            ++i;
            Swap(data[i], data[j]);
        }
    }

    Swap(data[i + 1], data[right]);

    return (i + 1);
}

int BadPartition(int* data, int left, int right) {
    int pivot = data[right];
    int i = (left - 1);

    for (int j = left; j <= right - 1; ++j)
    {
        if (data[j] <= pivot)
        {
            ++i;
            Swap(data[i], data[j]);
        }
    }

    Swap(data[i + 1], data[right]);

    return (i + 1);
}


void InsertSort(int *arr, int len) {
    for(int i = 1; i < len - 1; i++) {
        int j = i + 1;
        int tmp = arr[j];
        while(j > 0 && tmp > arr[j - 1]) {
            arr[j] = arr[j - 1];
            j--;
        }
        arr[j] = tmp;
    }
}


void BubbleSort(int *arr, int len) {
    for(int i = 0; i < len - 1; i++) {
        for(int j = 0; j < len - i - 1; j++) {
            if(arr[j + 1] < arr[j]) {
                int swap = arr[j + 1];
                arr[j + 1] = arr[j];
                arr[j] = swap;
            }
        }
    }
}


void HeapSort(int array[], int size){
    for (int i = size/2 - 1; i >= 0; i--) {
        repairTop(array, size - 1, i);
    }
    for (int i = size - 1; i > 0; i--) {
        swap(array, 0, i);
        repairTop(array, i - 1, 0);
    }
}


void repairTop(int array[], int bottom, int topIndex) {
    int tmp = array[topIndex];
    int succ = topIndex*2 + 1;
    if (succ < bottom && array[succ] > array[succ+1]) succ++;

    while (succ <= bottom && tmp > array[succ]) {
        array[topIndex] = array[succ];
        topIndex = succ;
        succ = succ*2 + 1;
        if (succ < bottom && array[succ] > array[succ+1]) succ++;
    }
    array[topIndex] = tmp;
}


void swap(int array[], int left, int right) {
    int tmp = array[right];
    array[right] = array[left];
    array[left] = tmp;
}