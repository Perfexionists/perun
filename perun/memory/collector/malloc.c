#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <time.h>

#include "backtrace.h"

#define LOG_FILE_NAME "MemoryLog"

static void* (*real_malloc)(size_t size);
static void* (*real_calloc)(size_t nmemb, size_t size);
static void* (*real_realloc)(void *ptr, size_t size);
static void  (*real_free)(void *ptr);
static void* (*real_memalign)(size_t alignment, size_t size);
static int   (*real_posix_memalign)(void** memptr, size_t alignment, size_t size);
static void* (*real_valloc)(size_t size);
static void* (*real_aligned_alloc)(size_t alignment, size_t size);

static FILE* logFile;
static int profiling = 0;
static int initialized = 0;

/*
GCC destructor attribute provides finalizing function which close log file properly
after main program's execution finished
*/
__attribute__((destructor)) void finalize (void){
  
  profiling = 1;

  if(logFile != NULL) {
    fclose(logFile);
  }
}

/*
Function provides initializing of the allocators 
and opening log file
*/
void init(){

  profiling = 1;

  real_malloc = dlsym(RTLD_NEXT, "malloc");
  real_realloc = dlsym(RTLD_NEXT, "realloc");
  real_calloc = dlsym(RTLD_NEXT, "calloc");
  real_free = dlsym(RTLD_NEXT, "free");
  real_memalign = dlsym(RTLD_NEXT, "memalign");
  real_valloc = dlsym(RTLD_NEXT, "valloc");
  real_aligned_alloc = dlsym(RTLD_NEXT, "aligned_alloc");
  real_posix_memalign = dlsym(RTLD_NEXT, "posix_memalign");

  initialized = 1;

  char fileName[256];
  sprintf(fileName, "MemoryLog");
  logFile = fopen(fileName, "w");

  profiling = 0;
}

void* malloc(size_t size){

  if(!initialized){
    init();
  }

  void *ptr = real_malloc(size);
    
  if(!profiling && ptr != NULL){
    profiling = 1;

    fprintf(logFile, "time %fs\n", clock() / (double)CLOCKS_PER_SEC);
    fprintf(logFile, "malloc %liB %li\n", size, (long int)ptr);
    backtrace(logFile);
   
    profiling = 0;
  }

  return ptr;
}

void free(void *ptr){

  if(!initialized)
    init();

  real_free(ptr);
  
  if(!profiling){
    profiling = 1;

    fprintf(logFile, "time %fs\n", clock() / (double)CLOCKS_PER_SEC);
    fprintf(logFile, "free 0B %li\n", (long int)ptr);
    backtrace(logFile);
  
    profiling = 0;
  }
}

void* realloc(void *ptr, size_t size){

  if(!initialized)
    init();

  void *nptr = real_realloc(ptr, size);

  if(!profiling && ptr != NULL){
      
    profiling = 1;
    
    fprintf(logFile, "time %fs\n", clock() / (double)CLOCKS_PER_SEC);  
    fprintf(logFile, "realloc %liB %li\n", size, (long int)nptr);
    backtrace(logFile);
    
    profiling = 0;
  }

  return nptr;
}

void* calloc(size_t nmemb, size_t size){

  if(!initialized)
    init();

  void *ptr = real_calloc(nmemb, size);
    
  if(!profiling && ptr != NULL){
      
    profiling = 1;
    
    fprintf(logFile, "time %fs\n", clock() / (double)CLOCKS_PER_SEC);
    fprintf(logFile, "calloc %liB %li\n", size*nmemb, (long int)ptr);
    backtrace(logFile);
    
    profiling = 0;
  }

  return ptr;
}

void* memalign(size_t alignment, size_t size){

  if(!initialized)
    init();

  void *ptr = real_memalign(alignment, size);

  if(!profiling && ptr != NULL){
      
    profiling = 1;
    
    fprintf(logFile, "time %fs\n", clock() / (double)CLOCKS_PER_SEC);
    fprintf(logFile, "memalign %liB %li\n", size, (long int)ptr);
    backtrace(logFile);
    
    profiling = 0;
  }

  return ptr;
}

int posix_memalign(void** memptr, size_t alignment, size_t size){

  if(!initialized)
    init();

  int ret = real_posix_memalign(memptr, alignment, size);

  if(!profiling && ret == 0){
      
    profiling = 1;
    
    fprintf(logFile, "time %fs\n", clock() / (double)CLOCKS_PER_SEC);
    fprintf(logFile, "posix_memalign %liB %li\n", size, (long int)*memptr);
    backtrace(logFile);
    
    profiling = 0;
  }

  return ret;
}

void* valloc(size_t size){

  if(!initialized)
    init();

  void *ptr = real_valloc(size);

  if(!profiling && ptr != NULL){
      
    profiling = 1;
    
    fprintf(logFile, "time %fs\n", clock() / (double)CLOCKS_PER_SEC);
    fprintf(logFile, "valloc %liB %li\n", size, (long int)ptr);
    backtrace(logFile);
    
    profiling = 0;
  }

  return ptr;
}

void *aligned_alloc(size_t alignment, size_t size){

  if(!initialized)
    init();

  void *ptr = real_aligned_alloc(alignment, size);

  if(!profiling && ptr != NULL){
      
    profiling = 1;
    
    fprintf(logFile, "time %fs\n", clock() / (double)CLOCKS_PER_SEC);
    fprintf(logFile, "aligned_alloc %liB %li\n", size, (long int)ptr);
    backtrace(logFile);
    
    profiling = 0;
  }

  return ptr;
}