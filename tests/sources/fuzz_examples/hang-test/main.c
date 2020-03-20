#include <assert.h>
#include <stdio.h>
#include <unistd.h>

#define REPS 100
#define SLEEP_TIME 1000

int main(int argc, char ** argv){
	FILE * fp = fopen(argv[1],"r");
	int num;
	fscanf(fp,"%d ",&num);
	if( num != 5 ){
		int i;
		for(i = 0; i < REPS; i++)
			usleep(SLEEP_TIME);
	}
	fclose(fp);
	return 0;
}
