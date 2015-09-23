
all: test.exe eparser.o etest.exe

eparser.o: eparser.h eparser.cpp
	g++ -o eparser.o -c -g -Wall -std=c++11 eparser.cpp

etest.exe: etest.cpp eparser.o
	g++ -o etest.exe -g -Wall -std=c++11 etest.cpp eparser.o

test.exe: test.o
	gcc -o test.exe test.o

test.o: test.c
	gcc -c test.c
    
clean:
	rm test.o test.exe eparser.o etest.exe
