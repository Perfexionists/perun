//notes: Compile requires -luwind 

#define UNW_LOCAL_ONLY
#include <stdio.h>
#include <libunwind.h>

void backtrace(void){

	char name[256];
	unw_cursor_t cursor;
	unw_context_t context;
	unw_word_t ip, sp, offset;

//Initialize cursor to current frame for local unwinding.
	unw_getcontext (&context);
	unw_init_local (&cursor, &context);

//Unwinding frames one by one, down througt the stack.
	while(unw_step(&cursor) > 0){

		char symbol[256];

	//Obtain instruction pointer
		if(unw_get_reg(&cursor, UNW_REG_IP, &ip) != 0)
	       	fprintf(stderr, "error: unw_get_reg (IP)\n");
	    if(ip == 0){
      	
      		break;
    	}
	//Obtain stack pointer    
		if(unw_get_reg(&cursor, UNW_REG_SP, &sp) != 0)
			fprintf(stderr, "error: unw_get_reg (SP)\n");

	//Obtain symbol name
	    unw_get_proc_name(&cursor, symbol, sizeof(symbol), &offset);

		printf("%s: ip = 0x%lx, sp = 0x%lx\n", symbol, ip, sp);
	}    
}