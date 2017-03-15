CC=g++
CFLAGS=-g -std=c++11 -pedantic -Wall -Wextra
CINSTR=-finstrument-functions

TST_SOURCE=test_workload/
#-finstrument-functions-exclude-file-list=stl_construct.h
#-finstrument-functions-exclude-function-list=vector
#-finstrument-functions-exclude-function-list=__static_initialization_and_destruction_0,_GLOBAL__sub_I__Z11SLList_initP6SLList

profile: main.o libprofile.so libprofapi.so
	$(CC) -o $(TST_SOURCE)profile main.o libprofile.so libprofapi.so

libprofile.so: profile.o config.o
	$(CC) $(CFLAGS) -shared -o libprofile.so profile.o config.o

libprofapi.so: profapi.o
	$(CC) $(CFLAGS) -shared -o libprofapi.so profapi.o

profapi.o: profile_api.cpp profile_api.h
	$(CC) $(CFLAGS) -c -fPIC -o profapi.o profile_api.cpp

profile.o: profile.cpp profile.h
	$(CC) $(CFLAGS) -c -fPIC -o profile.o profile.cpp

config.o: configuration.cpp configuration.h
	$(CC) $(CFLAGS) -c -fPIC -o config.o configuration.cpp

main.o: $(TST_SOURCE)main.cpp $(TST_SOURCE)SLList.h $(TST_SOURCE)SLListcls.h
	$(CC) $(CFLAGS) $(CINSTR) -c -o main.o $(TST_SOURCE)main.cpp

clean:
	rm -f *.o *.so $(TST_SOURCE)profile $(TST_SOURCE)trace.log

run:
	(cd $(TST_SOURCE) && LD_LIBRARY_PATH="../" ./profile)
# gedit trace.log
