# Cross-compile on Linux:   make            (needs gcc-mingw-w64-i686)
# Build on Windows (MSYS2): make CC=gcc
CC      ?= i686-w64-mingw32-gcc
HOSTCC  ?= cc
CFLAGS  ?= -O2 -Wall -Wextra
SRC      = src/main.c src/solver.c

all: SisenAutoSolver.exe

SisenAutoSolver.exe: $(SRC) src/solver.h
	$(CC) $(CFLAGS) -municode -mwindows -static -o $@ $(SRC)

test: src/test_solver.c src/solver.c src/solver.h
	$(HOSTCC) $(CFLAGS) -o test_solver src/test_solver.c src/solver.c
	./test_solver

clean:
	rm -f SisenAutoSolver.exe test_solver

.PHONY: all test clean
