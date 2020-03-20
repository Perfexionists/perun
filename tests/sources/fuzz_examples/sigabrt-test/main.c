#include <assert.h>
#include <stdio.h>
#include <unistd.h>
int main(int argc, char ** argv){
	
	FILE * fp = fopen(argv[1],"r");
	int num;
	fscanf(fp,"%d ",&num);
	assert( num == 5 );
}
