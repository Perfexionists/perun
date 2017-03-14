#ifndef CPP_BASIC_SLLIST_H
#define CPP_BASIC_SLLIST_H

#include "../profile_api.h"

struct SLLelem {
    int key;
    SLLelem *next;
};

struct SLList {
    SLLelem *head;
    SLLelem *tail;
    size_t size;
};

void SLList_init(SLList *list) {
    list->head = nullptr;
    list->tail = nullptr;
    list->size = 0;
}

void SLList_insert(SLList *list, int num) {
    SLLelem *elem = new SLLelem;
    elem->key = num;
    elem->next = nullptr;
    if(list->head == nullptr) {
        list->head = elem;
    } else {
        list->tail->next = elem;
    }
    list->tail = elem;
    list->size++;
}

void SLList_remove(SLList *list, int key) {
    SLLelem *tmp = list->head;
    SLLelem *prev = nullptr;
    while(tmp != nullptr) {
        if(key == tmp->key) {
            if(tmp == list->head) {
                list->head = tmp->next;
            } else if(tmp == list->tail) {
                list->tail = prev;
                prev->next = nullptr;
            } else {
                prev->next = tmp->next;
            }
            delete tmp;
            list->size--;
            return;
        } else {
            prev = tmp;
            tmp = tmp->next;
        }
    }
}

SLLelem *SLList_search(SLList *list, int key) {
    SLLelem *tmp = list->head;
    while(tmp != nullptr) {
        if(key == tmp->key) {
            return tmp;
        } else {
            tmp = tmp->next;
        }
    }
    return nullptr;
}

void SLList_destroy(SLList *list) {
    SLLelem *tmp = list->head;
    while(tmp != nullptr) {
        list->head = tmp->next;
        delete tmp;
        tmp = list->head;
    }
    list->size = 0;
}

#endif //CPP_BASIC_SLLIST_H
