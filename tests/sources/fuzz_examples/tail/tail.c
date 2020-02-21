/**
  tail.c
  Riešenie IJC-DU2, príklad a), 23.4.2017
  Autor: Matúš Liščinský, FIT
  Login: xlisci02
  Preložené: gcc 5.4.0 (merlin)
  Program pre vypis poslednych n riadkov zo suboru viz. POSIX tail.
**/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LIMIT 1024

/*
* Funkcia process_arguments sluzi na:
* Spracovanie argumentov
* V pripade uspechu vracia pocet skontrolovanych argumentov +1 (nulty argument)
* Ak nastane chyba vracia -1
*/
int process_arguments(int argc, char * argv[], long * number , FILE ** file)
{
	if(argc > 4 || argc < 1) // nespravny pocet argumentov
	{
		fprintf (stderr, "[ERR] Chybny pocet argumentov\n");
		return -1;
	}
	else if (argc == 1) // ziaden argument nebol zadany, vraciam argc
	{
		return argc;
	}
	
	else if(argc == 2)
	{
		* file = fopen (argv[1],"r");

		if (* file==NULL) 
		{
			if((strcmp(argv[1],"-n")==0)) // Program spusteny s -n bez doplnujuceho parametra
				fprintf(stderr,"[ERR] Parameter -n vyzaduje dalsi parameter [cislo >=0]\n");
			else
				fprintf(stderr,"[ERR] Nepodarilo sa otvorit subor %s \n",argv[1]);
			return -1;
		}
		return argc;
	}

	else if(argc == 3) 
	{
		char * ptr = NULL;
		* number = strtol(argv[2],&ptr,10);
		
		if( strcmp(argv[1],"-n")==0 && *ptr =='\0' && *number >= 0)
			return argc;	
		else 
		{
			fprintf(stderr,"[ERR] Chybne argumenty [%s %s] \n",argv[1], argv[2]);
			return -1;
		}	
	}
	else //(argc == 4)
	{
		
		* file = fopen (argv[3],"r");

		if (* file==NULL)
		{	
				fprintf(stderr,"[ERR] Nepodarilo sa otvorit subor %s\n",argv[3]);
				return -1;	
		} 
		
		char * ptr = NULL;
		* number = strtol(argv[2],&ptr,10);
		
		if( strcmp(argv[1],"-n")==0 && *ptr =='\0' && *number >= 0)
			return argc;	
		else 
		{
			if(* file !=stdin && fclose(* file) == EOF)
				fprintf(stderr,"[WARNING] Nepodarilo sa zatvorit subor %s\n",argv[3]);
			fprintf(stderr,"[ERR] Chybne argumenty [%s %s %s] \n",argv[1], argv[2], argv[3]);
			return -1;
		}		

	}
	
}

/*
* Funkcia free_array sluzi na:
* Uvolnenie alokovaneho miesta  
*/
void free_array(char ** str, long n)
{
	if(str!=NULL)
	for (int i = 0; i < n; i++)
		free(str[i]);
	free(str);
}

/*
* Funkcia shift sluzi na:
* Posunutie prvkov 'pola' pre pridanie na koniec 
* Vola sa v pripade ze pocet riadkov v subore je vacsi ako 
* pocet riadkov, ktore chceme vypisat.
*/
void shift(char ** str , long number_of_rows)
{
	// uschovanie ukazatela nulteho prvku pola
	char *tmp;
	tmp=str[0];
	
	for (int i=1; i<number_of_rows;i++)
		str[i-1]=str[i];
	
	// vvyuzitie uschovaneho ukazatela 
	str[number_of_rows-1]=tmp;
}

/*
* Funkcia alloc_memory sluzi na:
* Alokaciu miesta pre ukazatele na char * 
* V pripade uspechu vracia ukazatel na alokovane miesto
* inak vracia NULL
*/
char ** alloc_memory(long number_of_rows,char * filename, FILE ** file )
{
	char ** str=(char **)malloc(number_of_rows*(sizeof(char *)));
	
	if(str==NULL)
	{	
		free_array(str,0);
		if(* file !=stdin && fclose(* file) == EOF)
				fprintf(stderr,"[WARNING] Nepodarilo sa zatvorit subor %s\n",filename);
		fprintf(stderr,"Nepodarilo sa alokovat miesto\n");
		return NULL;
	}

	for (int i=0; i<number_of_rows;i++)
	{	
		str[i]=(char *)malloc(sizeof(char)*(LIMIT+2));
		if(str[i]==NULL)
		{	
			free_array(str,i);
			if(* file !=stdin && fclose(* file) == EOF)
				fprintf(stderr,"[WARNING] Nepodarilo sa zatvorit subor %s\n",filename);
			fprintf(stderr,"Nepodarilo sa alokovat miesto\n");
			return NULL;
		}
	}
	return str;
}	

/*
* Funkcia process_input sluzi na:
* Spracovanie vstupneho suboru
* Mozog tohto programu
* V pripade uspechu vracia pocet riadkov, kt. sa maju vypisat
* inak vracia -1
*/
int process_input(char ** strings,long number_of_rows,char * filename, FILE ** file )
{

	// pocet nacitanych riadkov
	int p=0;
	
	// do premennej 'c' sa uklada znak
	int c;

	// pocitadlo nacitanych znakov
	int znak=0;

	// flag pre signalizaciu prekrocenia limitu dlzky riadku
	int overfull=0;
	
	// Premenna pre docasne ukladanie retazca
	char *tmp=(char *)malloc(sizeof(char)*(LIMIT+2));
	
	if(tmp==NULL)
	{	
		free_array(strings,number_of_rows);
		if(* file !=stdin && fclose(* file) == EOF)
				fprintf(stderr,"[WARNING] Nepodarilo sa zatvorit subor %s\n",filename);
		fprintf(stderr,"Nepodarilo sa alokovat miesto\n");
		return -1;
	}

	// Nacitavanie vstupneho suboru po znaku, druha cas podmienky je pre nestandard. subor
	while ((c=getc(* file))!=EOF || strcmp(tmp,"")!=0)
	{
		// citaj dokym nenarazis na novy riadok alebo na koniec suboru
		if((c!='\n' && !feof(* file))) 
		{	
			if(znak<LIMIT)
			{
				char str [2]="\0";
				str [0]=c;
				strcat(tmp,str);
				znak++;
			}
			else 
				overfull=1;
		}

		// Ak sa nacita novy riadok alebo sme na konci a nieco nam ostalo v str, v pripade potreby 
		// prebehne posun (shift) a nacitany retazec sa zapise 
		
		if (c=='\n' || feof(* file))
		{
			if(p == number_of_rows)
			{	
				p--;
				shift(strings,number_of_rows);
			}	
			if(tmp[znak]!='\n' && znak!=0 && !feof(* file)) // doplnenie '\n' za retazec ak mu chyba
				strcat(tmp,"\n");
			if(znak==0 && c=='\n')	// ak je to prazdny riadok, nepreslo prvou podmienkou, manualne vkladanie '\n'
				strcpy(tmp,"\n");
			strings[p]=strcpy(strings[p],tmp);
			p++;
			znak=0;
			strcpy(tmp,"");

			// bez tejto podmienky pri nestandard. subore nutne 3x Ctrl + D (1 naviac pre testovanie podmienky)
			if(feof(* file))
				break;
		}
	}

	// AK sa prekrocil max. limit dlzky riadku
	if(overfull)
		fprintf(stderr, "[WARNING] Niektory riadok bol prilis dlhy a bol skrateny.\n");
	
	free(tmp);
	return p;
}

/*
* Funkcia main
* Vola vyssie implementovane funkcie a na zaver vykona vypis
*/

int main (int argc, char * argv[])
{

	long lines_sum=10;
	FILE * file = NULL;
	int ARG = process_arguments(argc, argv, &lines_sum, &file);
	
	// ARG sa musi rovnat argc, inak doslo k chybe
	if(ARG!=argc)
		return 1;

	//Ak file == NULL, znamena ze uzivatel nezadal subor -> citanie prebehne z stdin
	if (file == NULL)
		file = stdin;
	
	//Ak plati nic sa nema vypisat, iba cita znaky	
	if(lines_sum == 0)
	{
		while(getc(file)!=EOF);
		return 0;

	}
	//Alokovanie miesta pre ukazatele
	char ** strings= alloc_memory(lines_sum,argv[3],&file);
	if (strings==NULL)
		return 1;
	
	//Spracovanie vstupu
	int sum = process_input(strings,lines_sum,argv[3],&file);
	if(sum == -1)
		return 1;

	//Vypis
//	for(int i=0;i<sum;i++)
//	{	
//		printf("%s",strings[i]);
//	}

	//Zatvaranie suboru
	if(file !=stdin && fclose(file) == EOF)
		fprintf(stderr,"[WARNING] Nepodarilo sa zatvorit subor \n");
	
	//Uvolnenie miesta
	free_array(strings,lines_sum);
	return 0;

}
