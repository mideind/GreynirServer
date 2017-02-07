
all: libeparser.so etest.exe

libeparser.so: eparser.h eparser.cpp
	g++ -shared -o libeparser.so -Wall -fPIC -O3 -std=c++11 eparser.cpp

etest.exe: etest.cpp libeparser.so
	g++ -o etest.exe -g -Wall -std=c++11 ./libeparser.so etest.cpp

clean:
	rm libeparser.so etest.exe
