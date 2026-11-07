/* Host-side tests for solver.c: cc -O2 -o test_solver test_solver.c solver.c */
#include "solver.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* Independent reference: BFS over (cell, direction) counting turns on the padded grid. */
static int ref_connect(const int *board, int a, int b)
{
    enum { H = SS_ROWS + 2, W = SS_COLS + 2 };
    int best[H][W][4];
    int qr[H * W * 4 * 4], qc[H * W * 4 * 4], qd[H * W * 4 * 4], qt[H * W * 4 * 4];
    int head = 0, tail = 0, d;
    static const int dr[4] = { -1, 1, 0, 0 }, dc[4] = { 0, 0, -1, 1 };
    int ar = a / SS_COLS + 1, ac = a % SS_COLS + 1;
    int br = b / SS_COLS + 1, bc = b % SS_COLS + 1;

    memset(best, 0x7f, sizeof(best));
    for (d = 0; d < 4; d++) {
        qr[tail] = ar; qc[tail] = ac; qd[tail] = d; qt[tail] = 0; tail++;
        best[ar][ac][d] = 0;
    }
    while (head < tail) {
        int r = qr[head], c = qc[head], dir = qd[head], t = qt[head];
        head++;
        for (d = 0; d < 4; d++) {
            int nt = t + (d != dir), nr = r + dr[d], nc = c + dc[d];
            if (nt > 2 || nr < 0 || nr >= H || nc < 0 || nc >= W)
                continue;
            if (nr == br && nc == bc)
                return 1;
            if (nr >= 1 && nr <= SS_ROWS && nc >= 1 && nc <= SS_COLS &&
                board[(nr - 1) * SS_COLS + (nc - 1)] >= 0)
                continue;
            if (best[nr][nc][d] <= nt)
                continue;
            best[nr][nc][d] = nt;
            qr[tail] = nr; qc[tail] = nc; qd[tail] = d; qt[tail] = nt; tail++;
        }
    }
    return 0;
}

static void deal(int *board, unsigned *seed)
{
    int i;
    for (i = 0; i < SS_CELLS; i++)
        board[i] = i / 4; /* 36 kinds x 4 */
    for (i = SS_CELLS - 1; i > 0; i--) {
        int j, t;
        *seed = *seed * 1103515245u + 12345u;
        j = (int)((*seed >> 8) % (unsigned)(i + 1));
        t = board[i]; board[i] = board[j]; board[j] = t;
    }
}

int main(void)
{
    unsigned seed = 12345;
    int board[SS_CELLS];
    int g, games = 200, solved = 0, fail = 0;
    long checks = 0;
    clock_t t0;

    /* 1. Path rule agrees with the reference on random partially cleared boards. */
    for (g = 0; g < 300; g++) {
        int i, j;
        deal(board, &seed);
        for (i = 0; i < SS_CELLS; i++) {
            seed = seed * 1103515245u + 12345u;
            if ((seed >> 16) % 100 < (unsigned)(g % 90))
                board[i] = -1;
        }
        for (i = 0; i < SS_CELLS; i++) {
            if (board[i] < 0)
                continue;
            for (j = i + 1; j < SS_CELLS; j++) {
                if (board[j] < 0)
                    continue;
                checks++;
                if (ss_can_connect(board, i, j) != ref_connect(board, i, j)) {
                    printf("MISMATCH g=%d a=%d b=%d ss=%d ref=%d\n", g, i, j,
                           ss_can_connect(board, i, j), ref_connect(board, i, j));
                    fail = 1;
                }
            }
        }
    }
    printf("path rule: %ld pairs checked, %s\n", checks, fail ? "FAILED" : "ok");

    /* 2. Solver on random deals; every returned sequence is replayed and checked. */
    t0 = clock();
    for (g = 0; g < games; g++) {
        ss_result res;
        int copy[SS_CELLS], k;
        deal(board, &seed);
        ss_solve(board, 3000000, 5000, NULL, &res);
        memcpy(copy, board, sizeof(copy));
        for (k = 0; k < res.count; k++) {
            int a = res.moves[k].a, b = res.moves[k].b;
            if (copy[a] < 0 || copy[a] != copy[b] || !ref_connect(copy, a, b)) {
                printf("INVALID move %d in game %d\n", k, g);
                fail = 1;
                break;
            }
            copy[a] = copy[b] = -1;
        }
        if (res.solved) {
            for (k = 0; k < SS_CELLS; k++)
                if (copy[k] >= 0) {
                    printf("solved flag but board not empty in game %d\n", g);
                    fail = 1;
                    break;
                }
            solved++;
        }
    }
    printf("solver: %d/%d random deals cleared, %.2fs total\n", solved, games,
           (double)(clock() - t0) / CLOCKS_PER_SEC);
    return fail;
}
