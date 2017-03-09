/*
 * File:        backtrace.c
 * Project:     Library for Profiling and Visualization of Memory Consumption
 *              of C/C++ Programs, Bachelor's thesis
 * Date:        29.2.2017
 * Author:      Podola Radim, xpodol06@stud.fit.vutbr.cz
 * Description: File contains module for obtaining the stack trace.
 */
#define UNW_LOCAL_ONLY
#include <stdio.h>
#include <libunwind.h>

const int SYMBOL_LEN = 256;

void backtrace(FILE *log, unsigned skip){

   unw_cursor_t cursor;
   unw_context_t context;
   unw_word_t ip, offset;
   int ret = 0;

//Initialize cursor to current frame for local unwinding.
   if(unw_getcontext(&context) != 0){
      fprintf(stderr, "error: unw_getcontext\n");
      return;
   }
   if(unw_init_local(&cursor, &context) != 0){
      fprintf(stderr, "error: unw_init_local\n");
      return;      
   }

//Unwinding frames one by one, down througt the stack.
   while(unw_step(&cursor) > 0){

      char symbol[SYMBOL_LEN];

      if(skip > 0){
         skip--;
         continue;
      }

   //Obtain instruction pointer
      if(unw_get_reg(&cursor, UNW_REG_IP, &ip) != 0)
         fprintf(stderr, "error: unw_get_reg (IP)\n");
      if(ip == 0)
         break;

   //Obtain symbol name
      ret = unw_get_proc_name(&cursor, symbol, SYMBOL_LEN, &offset);
      if(ret != 0){
         if(ret == UNW_ENOINFO)
            fprintf(stderr, "error: (unw_get_proc_name) "
                            "Unable to determine the name of the procedure.\n");
         else
            fprintf(stderr, "error: (unw_get_proc_name) "
                            "An unspecified error occurred.\n");

         fprintf(log, "%s 0x%lx\n", "?", ip);

      }else{
         fprintf(log, "%s 0x%lx\n", symbol, ip);
      }
   }
}