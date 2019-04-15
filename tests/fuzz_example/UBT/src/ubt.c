//
//  BST.c
//  BST
//
//  Created by Will Salisbury on 5/21/14.
//  Copyright (c) 2014 Will Salisbury. All rights reserved.
//

#include <stdio.h>
#include <stdlib.h>
#include <math.h>


#include "ubt.h"

#pragma mark - Node

static bst_node_t* bst_create_node(const BSTType val);
static void bst_destroy_node(bst_node_t* node);
static void bst_insert_node(bst_node_t* root, const BSTType val);
static bool bst_remove_node(bst_node_t* root, const BSTType val);
static bool bst_find_node(bst_node_t* root, const BSTType val);
static void bst_print_nodes(bst_node_t* root);
static void bst_print_node(bst_node_t* root, int acc);
static size_t bst_node_depth(bst_node_t* root, size_t depth);

#pragma mark - BST

BST bst_create(void){
    BST new_bst = NULL;
    
    new_bst = (bst_t *)(malloc(sizeof(bst_t)));
    if (NULL == new_bst) {
        return NULL;
    }
    
    new_bst->root = NULL;
    
    return new_bst;
}

void bst_destroy(BST* tree){
    BST t = *tree;
    
    if (NULL == t || NULL == t->root) {
        return;
    }
    
    bst_destroy_node(t->root);
    t->root = NULL;
    free(t);
    *tree = NULL;
}

void bst_insert(BST tree, const BSTType val){
    if (NULL == tree) {
        return;
    }
    
    if(NULL == tree->root) {
        tree->root = bst_create_node(val);
        return;
    }
    
    bst_insert_node(tree->root, val);
}

bool bst_remove(BST tree, const BSTType val){
    if(NULL == tree || NULL == tree->root){
        return false;
    }
    
    return bst_remove_node(tree->root, val);
}

bool bst_find(const BST tree, const BSTType val){
    if(NULL == tree || NULL == tree->root){
        return false;
    }
    
    return bst_find_node(tree->root, val);
}

void bst_print(BST const tree){
    if (NULL == tree || NULL == tree->root) {
        return;
    }
    
    fprintf(stdout, "*****BST*****\n");
    bst_print_nodes(tree->root);
    fprintf(stdout, "\n\n");
    
    
}

size_t bst_depth(BST const tree){
    if (NULL == tree || NULL == tree->root) {
        return 0;
    }
    
    return bst_node_depth(tree->root, 0);
    
}

/* Private */

static bst_node_t* bst_create_node(const BSTType val){
    bst_node_t* new_node = NULL;
    
    new_node = (bst_node_t*)(malloc(sizeof(bst_node_t)));
    if(NULL == new_node){
        return NULL;
    }
    
    new_node->val = val;
    new_node->left = NULL;
    new_node->right = NULL;
    return new_node;
}


static void bst_destroy_node(bst_node_t* node){
    if (NULL == node) {
        return;
    }
    if (NULL != node->left) {
        bst_destroy_node(node->left);
        node->left = NULL;
    }
    if (NULL != node->right) {
        bst_destroy_node(node->right);
        node->right = NULL;
    }
    free(node);
}


static void bst_insert_node(bst_node_t* root, const BSTType val){
    if (NULL == root) {
        return;
    }
    
    if(val == root->val){
        return;
    }
    
    if (val < root->val) {
        if (NULL == root->left) {
            root->left = bst_create_node(val);
            return;
        } else {
            bst_insert_node(root->left, val);
        }
    }
    
    if (val > root->val) {
        if (NULL == root->right) {
            root->right = bst_create_node(val);
            return;
        } else {
            bst_insert_node(root->right, val);
        }
    }
    
}

static bool bst_remove_node(bst_node_t* root, const BSTType val){
    return false;
}

static bool bst_find_node(bst_node_t* root, const BSTType val){
    if (NULL == root) {
        return false;
    }
    
    if (val == root->val) {
        return true;
    } else if (val < root->val) {
        return bst_find_node(root->left, val);
    } else if (val > root->val) {
        return bst_find_node(root->right, val);
    }
    
    exit(EXIT_FAILURE);
    return false;
}


static void bst_print_nodes(bst_node_t* root){
    if(NULL == root){
        return;
    }
    
    bst_print_node(root, 0);
}

static void bst_print_node(bst_node_t* root, int acc){
    if (NULL == root) {
        return;
    }
    
    for(int iter = 0; iter < acc; ++iter){
        fprintf(stdout, "\t");
    }
    fprintf(stdout, "%d -> (\n", root->val);
    bst_print_node(root->left, acc+1);
    bst_print_node(root->right, acc+1);
    fprintf(stdout, ")");
    
    
}

static size_t bst_node_depth(bst_node_t* root, size_t depth){
    if (NULL == root) {
        return depth;
    }
    
    return (size_t)fmax(
                        bst_node_depth(root->left, depth+1),
                        bst_node_depth(root->right, depth+1)
                        );
}

