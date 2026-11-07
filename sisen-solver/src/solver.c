#include "solver.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/* A cell is passable when it is outside the board, empty, or one of the two endpoints. */
static int passable(const int *board, int r, int c, int a, int b)
{
    int i;
    if (r < 0 || r >= SS_ROWS || c < 0 || c >= SS_COLS)
        return 1;
    i = r * SS_COLS + c;
    return i == a || i == b || board[i] < 0;
}

static int col_clear(const int *board, int c, int r0, int r1, int a, int b)
{
    int r, lo = r0 < r1 ? r0 : r1, hi = r0 < r1 ? r1 : r0;
    for (r = lo; r <= hi; r++)
        if (!passable(board, r, c, a, b))
            return 0;
    return 1;
}

static int row_clear(const int *board, int r, int c0, int c1, int a, int b)
{
    int c, lo = c0 < c1 ? c0 : c1, hi = c0 < c1 ? c1 : c0;
    for (c = lo; c <= hi; c++)
        if (!passable(board, r, c, a, b))
            return 0;
    return 1;
}

int ss_can_connect(const int *board, int a, int b)
{
    int r1 = a / SS_COLS, c1 = a % SS_COLS;
    int r2 = b / SS_COLS, c2 = b % SS_COLS;
    int y, x;

    if (a == b)
        return 0;
    /*
     * Every path with at most two turns has a middle segment. Try each possible
     * horizontal middle row y (vertical legs on columns c1 and c2) and each
     * possible vertical middle column x (horizontal legs on rows r1 and r2),
     * including the margin row/column just outside the board.
     * Straight and one-turn paths are special cases of these.
     */
    for (y = -1; y <= SS_ROWS; y++) {
        if (col_clear(board, c1, r1, y, a, b) &&
            row_clear(board, y, c1, c2, a, b) &&
            col_clear(board, c2, y, r2, a, b))
            return 1;
    }
    for (x = -1; x <= SS_COLS; x++) {
        if (row_clear(board, r1, c1, x, a, b) &&
            col_clear(board, x, r1, r2, a, b) &&
            row_clear(board, r2, x, c2, a, b))
            return 1;
    }
    return 0;
}

int ss_list_moves(const int *board, ss_move *out)
{
    int n = 0, i, j;
    for (i = 0; i < SS_CELLS; i++) {
        if (board[i] < 0)
            continue;
        for (j = i + 1; j < SS_CELLS; j++) {
            if (board[j] != board[i])
                continue;
            if (ss_can_connect(board, i, j)) {
                out[n].a = i;
                out[n].b = j;
                n++;
            }
        }
    }
    return n;
}

/* ---- search ---------------------------------------------------------------- */

#define HASH_BITS 21
#define HASH_SIZE (1u << HASH_BITS)

typedef struct {
    int board[SS_CELLS];
    int kind_left[256];
    uint64_t zobrist[SS_CELLS];
    uint64_t hash;
    uint64_t *seen; /* open-addressing set of visited (failed) states */
    ss_move path[SS_MAX_PAIRS];
    int depth;
    int remaining;
    ss_result *res;
    long max_nodes;
    clock_t deadline;
    volatile const int *cancel;
    int stop;
} search_ctx;

static uint64_t splitmix(uint64_t *s)
{
    uint64_t z = (*s += 0x9E3779B97F4A7C15ull);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
}

/* Returns 1 if the state was already present, otherwise inserts it and returns 0. */
static int seen_check_insert(search_ctx *ctx, uint64_t h)
{
    uint32_t i;
    if (!ctx->seen)
        return 0;
    if (h == 0)
        h = 1;
    i = (uint32_t)(h & (HASH_SIZE - 1));
    while (ctx->seen[i]) {
        if (ctx->seen[i] == h)
            return 1;
        i = (i + 1) & (HASH_SIZE - 1);
    }
    ctx->seen[i] = h;
    return 0;
}

typedef struct {
    ss_move m;
    int score;
} scored_move;

static int cmp_scored(const void *x, const void *y)
{
    const scored_move *p = x, *q = y;
    return q->score - p->score;
}

static int should_stop(search_ctx *ctx)
{
    if (ctx->stop)
        return 1;
    if ((ctx->res->nodes & 1023) == 0) {
        if ((ctx->cancel && *ctx->cancel) ||
            (ctx->deadline && clock() > ctx->deadline))
            ctx->stop = 1;
    }
    if (ctx->max_nodes > 0 && ctx->res->nodes >= ctx->max_nodes)
        ctx->stop = 1;
    return ctx->stop;
}

static int dfs(search_ctx *ctx)
{
    ss_move raw[SS_CELLS * 2];
    scored_move list[SS_CELLS * 2];
    int n, i;

    if (ctx->remaining == 0)
        return 1;
    ctx->res->nodes++;
    if (should_stop(ctx))
        return 0;
    if (seen_check_insert(ctx, ctx->hash))
        return 0;

    n = ss_list_moves(ctx->board, raw);
    if (n == 0)
        return 0;

    for (i = 0; i < n; i++) {
        int kind = ctx->board[raw[i].a];
        int score = 0;
        /* Finishing a kind can never block anything else later. */
        if (ctx->kind_left[kind] == 2)
            score += 100;
        /* Tiles near the edge free up the outer routes; mild preference. */
        {
            int ra = raw[i].a / SS_COLS, ca = raw[i].a % SS_COLS;
            int rb = raw[i].b / SS_COLS, cb = raw[i].b % SS_COLS;
            int ea = ra == 0 || ra == SS_ROWS - 1 || ca == 0 || ca == SS_COLS - 1;
            int eb = rb == 0 || rb == SS_ROWS - 1 || cb == 0 || cb == SS_COLS - 1;
            score += (ea + eb);
        }
        list[i].m = raw[i];
        list[i].score = score;
    }
    qsort(list, (size_t)n, sizeof(list[0]), cmp_scored);

    for (i = 0; i < n; i++) {
        int a = list[i].m.a, b = list[i].m.b;
        int kind = ctx->board[a];

        ctx->board[a] = ctx->board[b] = -1;
        ctx->hash ^= ctx->zobrist[a] ^ ctx->zobrist[b];
        ctx->kind_left[kind] -= 2;
        ctx->remaining -= 2;
        ctx->path[ctx->depth++] = list[i].m;

        if (ctx->depth > ctx->res->count) {
            memcpy(ctx->res->moves, ctx->path, sizeof(ss_move) * (size_t)ctx->depth);
            ctx->res->count = ctx->depth;
        }

        if (dfs(ctx))
            return 1;

        ctx->depth--;
        ctx->remaining += 2;
        ctx->kind_left[kind] += 2;
        ctx->hash ^= ctx->zobrist[a] ^ ctx->zobrist[b];
        ctx->board[a] = ctx->board[b] = kind;

        if (ctx->stop)
            return 0;
    }
    return 0;
}

int ss_solve(const int *board, long max_nodes, int time_limit_ms,
             volatile const int *cancel, ss_result *result)
{
    search_ctx *ctx;
    uint64_t seed = 0x5153454E53455321ull;
    int i;

    memset(result, 0, sizeof(*result));
    ctx = calloc(1, sizeof(*ctx));
    if (!ctx)
        return 0;
    ctx->seen = calloc(HASH_SIZE, sizeof(uint64_t)); /* NULL just disables memoisation */
    ctx->res = result;
    ctx->max_nodes = max_nodes;
    ctx->cancel = cancel;
    if (time_limit_ms > 0)
        ctx->deadline = clock() + (clock_t)((double)time_limit_ms * CLOCKS_PER_SEC / 1000.0);

    for (i = 0; i < SS_CELLS; i++) {
        int k = board[i];
        ctx->zobrist[i] = splitmix(&seed);
        if (k >= 0 && k < 256) {
            ctx->board[i] = k;
            ctx->kind_left[k]++;
            ctx->remaining++;
            ctx->hash ^= ctx->zobrist[i];
        } else {
            ctx->board[i] = -1;
        }
    }

    result->solved = dfs(ctx);
    if (result->solved) {
        memcpy(result->moves, ctx->path, sizeof(ss_move) * (size_t)ctx->depth);
        result->count = ctx->depth;
    }

    free(ctx->seen);
    free(ctx);
    return result->solved;
}
