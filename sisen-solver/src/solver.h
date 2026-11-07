/*
 * Sisen (Shisen-Sho) board solver.
 *
 * Board layout matches "四川省 for Win" 2.13: 8 rows x 18 columns,
 * index = row * SS_COLS + col. A cell holds a tile kind (>= 0) or -1 when empty.
 * Two tiles of the same kind can be removed when they can be joined by a line of
 * at most three straight segments (two turns) that passes only through empty
 * cells; the line may run through the one-cell margin outside the board.
 */
#ifndef SISEN_SOLVER_H
#define SISEN_SOLVER_H

#define SS_ROWS 8
#define SS_COLS 18
#define SS_CELLS (SS_ROWS * SS_COLS)
#define SS_MAX_PAIRS (SS_CELLS / 2)

typedef struct {
    int a; /* cell index of the first tile */
    int b; /* cell index of the second tile */
} ss_move;

/* Nonzero when the tiles at cells a and b can be connected (kinds are not checked). */
int ss_can_connect(const int *board, int a, int b);

/* Lists every currently removable pair. Returns the count. out must hold SS_CELLS*2 entries. */
int ss_list_moves(const int *board, ss_move *out);

typedef struct {
    ss_move moves[SS_MAX_PAIRS];
    int count;        /* number of moves in moves[] */
    int solved;       /* 1 when moves[] clears the whole board */
    long nodes;       /* search nodes visited */
} ss_result;

/*
 * Searches for a sequence of removals that clears the board.
 * When no full solution is found within the limits, result holds the longest
 * sequence seen and solved is 0. Returns result->solved.
 * cancel may be NULL; when it points to a nonzero value the search stops early.
 */
int ss_solve(const int *board, long max_nodes, int time_limit_ms,
             volatile const int *cancel, ss_result *result);

#endif
