CC=g++
CFLAGS=-g -std=c++11 -pedantic -Wall -Wextra
CINSTR=-finstrument-functions

libs: libprofile.so libprofapi.so

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

clean:
	rm -f *.o *.so

