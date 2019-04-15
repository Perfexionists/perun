//
//  BST.h
//  BST
//
//  Created by Will Salisbury on 5/21/14.
//  Copyright (c) 2014 Will Salisbury. All rights reserved.
//

#ifndef BST_BST_h
#define BST_BST_h

#include <stdbool.h>

#pragma mark - Node

typedef int BSTType;

struct bst_node_s {
    BSTType val;
    struct bst_node_s* left;
    struct bst_node_s* right;
};

typedef struct bst_node_s bst_node_t;

struct bst_s {
    bst_node_t* root;
};

typedef struct bst_s bst_t;
typedef bst_t* BST;

BST bst_create(void);
void bst_destroy(BST* tree);
void bst_insert(BST tree, BSTType const val);
bool bst_remove(BST tree, BSTType const val);
bool bst_find(const BST tree, BSTType const val);
void bst_print(BST const tree);
size_t bst_depth(BST const tree);


//static bst_node_t* bst_create_node(const BSTType val);
//static void bst_destroy_node(bst_node_t* node);
//static void bst_insert_node(const BSTType val);
//static bool bst_remove_node(BSTType const val);
//static bool bst_find_node(BSTType const val);
//static void bst_print_node(bst_node_t* const node);

#endif
