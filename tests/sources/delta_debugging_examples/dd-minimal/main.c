#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>

#define MAGIC_NUMBER 100
#define BUFFER_SIZE 256

void magicLoop() {
    for (int i = 0; i < MAGIC_NUMBER; ++i) {
        usleep(500000);
    }
}

void checkInputString(const char* inputString) {
    int count = 0;
    for (int i = 0; inputString[i] != '\0'; ++i) {
        char character = inputString[i];
        if (character == '-') {
            ++count;
            if (count == 3) {
                magicLoop();
            }
        }
    }
}

int main(int argc, char* argv[]) {
    if (argc != 2) {
        return 1;
    }

    FILE * fp = fopen(argv[1],"r");

    if (fp == NULL) {
        printf("Error opening file\n");
        return 1;
    }

    char fileContent[BUFFER_SIZE];

    while (fscanf(fp, "%255s", fileContent) == 1) {

        printf("read line: %s\n", fileContent);
    }

    fclose(fp);
    checkInputString(fileContent);
    return 0;
}
