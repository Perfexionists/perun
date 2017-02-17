#ifndef CPP_BASIC_SLLISTCLS_H
#define CPP_BASIC_SLLISTCLS_H

class SLListcls {
    class SLLelemcls;

    SLLelemcls *head;
    SLLelemcls *tail;

    class SLLelemcls {
    public:
        int key;
        SLLelemcls *next;

        SLLelemcls(int key) {
            this->key = key;
            next = nullptr;
        };
    };

public:
    SLListcls() {
        head = nullptr;
        tail = nullptr;
    }

    ~SLListcls() {
        SLLelemcls *tmp = head;
        while(tmp != nullptr) {
            head = tmp->next;
            delete tmp;
            tmp = head;
        }
    }

    void Insert(int num) {
        SLLelemcls *elem = new SLLelemcls(num);
        if(head == nullptr) {
            head = elem;
        } else {
            tail->next = elem;
        }
        tail = elem;
    };

    void Remove(int key) {
        SLLelemcls *tmp = head;
        SLLelemcls *prev = nullptr;
        while(tmp != nullptr) {
            if(key == tmp->key) {
                if(tmp == head) {
                    head = tmp->next;
                } else if(tmp == tail) {
                    tail = prev;
                    prev->next = nullptr;
                } else {
                    prev->next = tmp->next;
                }
                delete tmp;
                return;
            } else {
                prev = tmp;
                tmp = tmp->next;
            }
        }
    }

    SLLelemcls *Search(int key) {
        SLLelemcls *tmp = head;
        while(tmp != nullptr) {
            if(key == tmp->key) {
                return tmp;
            } else {
                tmp = tmp->next;
            }
        }
        return nullptr;
    }
};

#endif //CPP_BASIC_SLLISTCLS_H
