CC=g++
CFLAGS=-g

all:
	$(CC) $(CFLAGS) quicksort.cpp -o ./quicksort
	echo ./build/ ./build/_build/ ./testdir/ ./testdir/nobuild | xargs -n 1 cp ./quicksort

clean:
	echo ./quicksort ./build/quicksort ./build/_build/quicksort ./testdir/quicksort ./testdir/nobuild/quicksort | xargs -n 1 rm -f
