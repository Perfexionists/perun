/*
 * File:        malloc.c
 * Project:     Library for Profiling and Visualization of Memory Consumption
 *              of C/C++ Programs, Bachelor's thesis
 * Date:        29.2.2017
 * Author:      Podola Radim, xpodol06@stud.fit.vutbr.cz
 * Description: File contains implementations of injected allocation functions.
 *
 * Note that this instrumentation was remodelled with great inspiration of the following project
 * (https://github.com/jtolds/malloc_instrumentation). Many thanks to authors for providing
 * a neat solution to the issues with dlsym() or fprintf() allocations (mostly that came with
 * upgrade to Ubuntu 18.04)
 */
#define _GNU_SOURCE
#include <dlfcn.h> //dlsym()
#include <stdio.h>
#include <stdlib.h>
#include <time.h> //clock()
#include <stdbool.h>

#include "backtrace.h"

// File name of the log file
#define LOG_FILE_NAME "MemoryLog"
// 0 - full backtrace log
// 1 - omitting function log_allocation() from backtrace log
// 2 - omitting allocation functions from backtrace log
#define CALLS_TO_SKIP 1

static FILE *logFile = NULL;

__thread unsigned int mutex = 0;

/**
 * Locks mutex for profiling, to prevent cycles if anything during profiling needs to allocate
 * something.
 *
 * @return: value of the mutex
 */
int lock_mutex() {
    return __sync_fetch_and_add(&mutex, 1);
}

/**
 * Unlocks the mutex
 */
void unlock_mutex() {
    __sync_fetch_and_sub(&mutex, 1);
}

/* Pointers to original allocation/free functions */
static void *(*real_malloc)(size_t) = NULL;
static void  (*real_free)(void*) = NULL;
static void *(*real_realloc)(void*, size_t) = NULL;
static void *(*real_calloc)(size_t, size_t)= NULL;
static void *(*real_memalign)(size_t, size_t) = NULL;
static int   (*real_posix_memalign)(void**, size_t, size_t) = NULL;
static void *(*real_valloc)(size_t) = NULL;
static void *(*real_aligned_alloc)(size_t, size_t) = NULL;

/* Pointers to temporary points */
static void *(*temp_malloc)(size_t) = NULL;
static void  (*temp_free)(void*) = NULL;
static void *(*temp_realloc)(void*, size_t) = NULL;
static void *(*temp_calloc)(size_t, size_t)= NULL;
static void *(*temp_memalign)(size_t, size_t) = NULL;
static int   (*temp_posix_memalign)(void**, size_t, size_t) = NULL;
static void *(*temp_valloc)(size_t) = NULL;
static void *(*temp_aligned_alloc)(size_t, size_t) = NULL;

/* Helper functions, courtesy of https://github.com/jtolds/malloc_instrumentation */
char tmpbuf[1024];
unsigned long tmppos = 0;
unsigned long tmpallocs = 0;

/**
 * Dummy static allocator used to allocate memory using malloc before libmalloc.so is properly
 * loaded .
 *
 * @param size: size of allocated bytes
 * @return: pointer to allocated data
 */
void* dummy_malloc(size_t size) {
    if (tmppos + size >= sizeof(tmpbuf)) exit(1);
    void *retptr = tmpbuf + tmppos;
    tmppos += size;
    ++tmpallocs;
    return retptr;
}

/**
 * Dummy static allocator used to allocate memory using calloc before libmalloc.so is properly
 * loaded .
 *
 * @param nmemb: number of members in the allocated memory
 * @param size: size of allocated bytes
 * @return: pointer to allocated data
 */
void* dummy_calloc(size_t nmemb, size_t size) {
    void *ptr = dummy_malloc(nmemb * size);
    unsigned int i = 0;
    for (; i < nmemb * size; ++i)
        *((char*)((char*)ptr + i)) = '\0';
    return ptr;
}

/**
 * Dummy static free. Does nothing.
 */
void dummy_free(void *ptr) {}

/**
 * Initialization of the shared library.
 *
 * During the initialization we first set allocators to its dummy version, in case dlsym() or other
 * function needs to allocate any data. Then we try to use dlsym() to dynamically load original
 * versions of allocators. If we are successful we set the real_ pointers to these original version.
 * At last the log is initialized.
 */
__attribute__ ((constructor)) void initialize (void) {
    lock_mutex();
    real_malloc =         dummy_malloc;
    real_free =           dummy_free;
    real_realloc =        NULL;
    real_calloc =         dummy_calloc;
    real_memalign =       NULL;
    real_posix_memalign = NULL;
    real_valloc =         NULL;
    real_aligned_alloc =  NULL;

    temp_malloc =         dlsym(RTLD_NEXT, "malloc");
    temp_free =           dlsym(RTLD_NEXT, "free");
    temp_realloc =        dlsym(RTLD_NEXT, "realloc");
    temp_calloc =         dlsym(RTLD_NEXT, "calloc");
    temp_memalign =       dlsym(RTLD_NEXT, "memalign");
    temp_posix_memalign = dlsym(RTLD_NEXT, "posix_memalign");
    temp_valloc =         dlsym(RTLD_NEXT, "valloc");
    temp_aligned_alloc =  dlsym(RTLD_NEXT, "aligned_alloc");

    if(!temp_malloc || !temp_free || !temp_realloc || !temp_calloc
        || !temp_memalign || !temp_posix_memalign || !temp_valloc || !temp_aligned_alloc) {
        fprintf(stderr, "error: dlsym() failed for allocation function: %s\n", dlerror());
        exit(EXIT_FAILURE);
    }
    real_malloc =         temp_malloc;// this will be needed
    real_free =           temp_free; // this will be needed
    real_realloc =        temp_realloc;
    real_calloc =         temp_calloc; // this will be needed
    real_memalign =       temp_memalign;
    real_posix_memalign = temp_posix_memalign;
    real_valloc =         temp_valloc;
    real_aligned_alloc =  temp_aligned_alloc;

    if(!logFile) {
       logFile = fopen(LOG_FILE_NAME, "w");
       if(logFile == NULL){
          fprintf(stderr, "error: fopen()\n");
          exit(EXIT_FAILURE);
       }
    }
    unlock_mutex();
}

/**
 * GCC destructor attribute provides finalizing function which close log file properly after main
 * program's execution finished
 */
__attribute__((destructor)) void finalize (void) {
    if(logFile != NULL){
        fprintf(logFile, "EXIT %fs\n", clock() / (double)CLOCKS_PER_SEC);
        // FIXME: This is causing segfaults for some reason, hotfix
        // fclose(logFile);
    }
}

/**
 * Writes single allocation metadata to the log file.
 *
 * @param allocator: name of the allocator that did the allocation
 * @param size: size of the allocated data
 * @param ptr: pointer to the allocated data
 **/
void log_allocation(char *allocator, size_t size, void *ptr){
    unsigned int locked = lock_mutex();
    if(!locked && ptr != NULL) {
        fprintf(logFile, "time %fs\n", clock() / (double)CLOCKS_PER_SEC);
        fprintf(logFile, "%s %luB %li\n", allocator, (unsigned long) size, (long int)ptr);
        backtrace(logFile, CALLS_TO_SKIP);
        fprintf(logFile, "\n");
    }
    unlock_mutex();
}

/* Redefinitions of the standard allocation functions */
void *malloc(size_t size){
    void *ptr = real_malloc(size);
    log_allocation("malloc", size, ptr);
    return ptr;
}

void free(void *ptr){
    real_free(ptr);
    log_allocation("free", 0, ptr);
}

void *realloc(void *ptr, size_t size){
    void *old_ptr = ptr;
    void *nptr = real_realloc(ptr, size);

    log_allocation("realloc", size, nptr);
    if(nptr) {
        log_allocation("free", 0, old_ptr);
    }

    return nptr;
}

void *calloc(size_t nmemb, size_t size){
    void *ptr = real_calloc(nmemb, size);
    log_allocation("calloc", size*nmemb, ptr);
    return ptr;
}

void *memalign(size_t alignment, size_t size){
    void *ptr = real_memalign(alignment, size);
    log_allocation("memalign", size, ptr);
    return ptr;
}

int posix_memalign(void** memptr, size_t alignment, size_t size){
    int ret;
    if(ret = !real_posix_memalign(memptr, alignment, size)){
        log_allocation("posix_memalign", size, *memptr);
    }
    return ret;
}

void *valloc(size_t size){
    void *ptr = real_valloc(size);
    log_allocation("valloc", size, ptr);
    return ptr;
}

void *aligned_alloc(size_t alignment, size_t size){
    void *ptr = real_aligned_alloc(alignment, size);
    log_allocation("aligned_alloc", size, ptr);
    return ptr;
}