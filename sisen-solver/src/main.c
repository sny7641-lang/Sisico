/*
 * Sisen Auto Solver - automatically clears "四川省 for Win" 2.13 (Sisen.exe by ONO Shinji).
 *
 * How it works
 *   1. Finds the Sisen main window and its process.
 *   2. Locates the game's CMainWnd object in the process memory and reads the board
 *      (8x18 ints at +0xF8, -1 = empty) and the tile-kind table (bytes at +0x7B8).
 *   3. Solves the board with a depth-first search (solver.c).
 *   4. Plays the solution by posting WM_LBUTTONDOWN/UP to the game window
 *      (the real mouse cursor is not moved).
 *
 * The game marks a game as "assisted" when Search/Undo is used and then does not save
 * the record to the rank file. This tool sets that same flag, so automated games are
 * never recorded in the local ranking or offered for the world ranking.
 *
 * Offsets below were taken from Sisen.exe 2.13 (image base 0x400000, no relocations).
 */
#ifndef UNICODE
#define UNICODE
#endif
#ifndef _UNICODE
#define _UNICODE
#endif
#include <windows.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

#include "solver.h"

/* ---- Sisen.exe 2.13 layout ---------------------------------------------------- */

#define SISEN_VTABLE        0x004339A8u /* vtable of the main window object         */
#define SISEN_G_ORIGIN_X    0x0043F0D8u /* board origin x in client coordinates      */
#define SISEN_G_ORIGIN_Y    0x0043F0DCu /* board origin y                            */
#define SISEN_G_CELL_W      0x0043F104u /* tile cell width                           */
#define SISEN_G_CELL_H      0x0043F108u /* tile cell height                          */
#define SISEN_G_SSN         0x0043F0D0u /* "ssn" (save-game extension), used as id   */

#define OFF_HWND            0x001C      /* CWnd::m_hWnd                              */
#define OFF_BOARD           0x00F8      /* int[8*18], tile id or -1                  */
#define OFF_KIND            0x07B8      /* BYTE[144], kind of each tile id           */
#define OFF_ASSISTED        0x1274      /* set by Search/Undo: record is not saved   */
#define OFF_SEL_COL         0x128C
#define OFF_SEL_ROW         0x1290
#define OFF_STATE           0x12B8      /* 1 idle, 2 one tile selected, 3 removing   */
#define OBJ_READ_SIZE       0x12C0

#define ST_IDLE     1
#define ST_SELECTED 2
#define ST_REMOVING 3

#define CMD_GAME_START 40004            /* Game > Start (F2) */

/* Code bytes checked to make sure this is the supported version. */
static const struct { DWORD addr; BYTE bytes[8]; int len; } g_signature[] = {
    { 0x00405279, { 0x8B, 0x86, 0x90, 0x12, 0x00, 0x00 }, 6 },             /* ApSameCheck  */
    { 0x00405189, { 0x8B, 0x86, 0xB8, 0x12, 0x00, 0x00 }, 6 },             /* ApMouseClick */
    { 0x0040510C, { 0x8B, 0x35, 0xD8, 0xF0, 0x43, 0x00 }, 6 },             /* ApMouseRect  */
};

/* ---- game access --------------------------------------------------------------- */

typedef struct {
    HWND hwnd;
    HANDLE process;
    DWORD obj;      /* address of the CMainWnd object in the game process */
} game_t;

typedef struct {
    int board[SS_CELLS]; /* kinds, -1 empty */
    int state;
    int sel_col, sel_row;
    int assisted;
    int ox, oy, cw, ch;
} snapshot_t;

static int rpm(HANDLE p, DWORD addr, void *buf, SIZE_T len)
{
    SIZE_T got = 0;
    return ReadProcessMemory(p, (LPCVOID)(ULONG_PTR)addr, buf, len, &got) && got == len;
}

static int rpm_dword(HANDLE p, DWORD addr, DWORD *out)
{
    return rpm(p, addr, out, sizeof(*out));
}

static int check_signature(HANDLE p)
{
    char ssn[4];
    size_t i;
    if (!rpm(p, SISEN_G_SSN, ssn, sizeof(ssn)) || memcmp(ssn, "ssn", 4) != 0)
        return 0;
    for (i = 0; i < sizeof(g_signature) / sizeof(g_signature[0]); i++) {
        BYTE buf[8];
        if (!rpm(p, g_signature[i].addr, buf, (SIZE_T)g_signature[i].len) ||
            memcmp(buf, g_signature[i].bytes, (size_t)g_signature[i].len) != 0)
            return 0;
    }
    return 1;
}

static int board_looks_valid(const BYTE *obj)
{
    int i;
    for (i = 0; i < SS_CELLS; i++) {
        int v;
        memcpy(&v, obj + OFF_BOARD + i * 4, 4);
        if (v < -1 || v >= SS_CELLS)
            return 0;
    }
    return 1;
}

/* Scans the writable memory of the game for the main window object. */
static DWORD find_main_object(HANDLE p, HWND hwnd)
{
    MEMORY_BASIC_INFORMATION mbi;
    ULONG_PTR addr = 0x10000;
    BYTE *buf = NULL;
    SIZE_T bufsize = 0;
    DWORD found = 0;

    while (addr < 0x7FFF0000 &&
           VirtualQueryEx(p, (LPCVOID)addr, &mbi, sizeof(mbi)) == sizeof(mbi)) {
        ULONG_PTR base = (ULONG_PTR)mbi.BaseAddress;
        SIZE_T size = mbi.RegionSize;
        int ok = mbi.State == MEM_COMMIT &&
                 !(mbi.Protect & (PAGE_GUARD | PAGE_NOACCESS)) &&
                 (mbi.Protect & (PAGE_READWRITE | PAGE_EXECUTE_READWRITE | PAGE_WRITECOPY));
        if (ok && size <= 64u * 1024 * 1024) {
            SIZE_T got = 0, off;
            if (size > bufsize) {
                free(buf);
                buf = malloc(size);
                bufsize = buf ? size : 0;
            }
            if (buf && ReadProcessMemory(p, (LPCVOID)base, buf, size, &got) && got >= 4) {
                for (off = 0; off + 4 <= got; off += 4) {
                    DWORD v;
                    memcpy(&v, buf + off, 4);
                    if (v != SISEN_VTABLE)
                        continue;
                    {
                        BYTE obj[OBJ_READ_SIZE];
                        DWORD h;
                        DWORD cand = (DWORD)(base + off);
                        if (!rpm(p, cand, obj, sizeof(obj)))
                            continue;
                        memcpy(&h, obj + OFF_HWND, 4);
                        if ((HWND)(ULONG_PTR)h == hwnd && board_looks_valid(obj)) {
                            found = cand;
                            break;
                        }
                    }
                }
            }
        }
        if (found)
            break;
        addr = base + size;
        if (size == 0)
            break;
    }
    free(buf);
    return found;
}

typedef struct {
    game_t *game;
    int found_other_version;
} enum_ctx;

static BOOL CALLBACK enum_proc(HWND hwnd, LPARAM lp)
{
    enum_ctx *ec = (enum_ctx *)lp;
    DWORD pid = 0;
    HANDLE p;

    if (!IsWindowVisible(hwnd) || GetWindow(hwnd, GW_OWNER) != NULL)
        return TRUE;
    GetWindowThreadProcessId(hwnd, &pid);
    if (pid == 0 || pid == GetCurrentProcessId())
        return TRUE;
    p = OpenProcess(PROCESS_VM_READ | PROCESS_VM_WRITE | PROCESS_VM_OPERATION |
                    PROCESS_QUERY_INFORMATION, FALSE, pid);
    if (!p)
        return TRUE;
    {
        char ssn[4];
        if (rpm(p, SISEN_G_SSN, ssn, 4) && memcmp(ssn, "ssn", 4) == 0 && !check_signature(p))
            ec->found_other_version = 1;
    }
    if (check_signature(p)) {
        DWORD obj = find_main_object(p, hwnd);
        if (obj) {
            ec->game->hwnd = hwnd;
            ec->game->process = p;
            ec->game->obj = obj;
            return FALSE;
        }
    }
    CloseHandle(p);
    return TRUE;
}

/* Returns 1 on success, 0 when not found, -1 when a different Sisen version is running. */
static int find_game(game_t *g)
{
    enum_ctx ec;
    memset(g, 0, sizeof(*g));
    ec.game = g;
    ec.found_other_version = 0;
    EnumWindows(enum_proc, (LPARAM)&ec);
    if (g->process)
        return 1;
    return ec.found_other_version ? -1 : 0;
}

static void close_game(game_t *g)
{
    if (g->process)
        CloseHandle(g->process);
    memset(g, 0, sizeof(*g));
}

static int read_snapshot(game_t *g, snapshot_t *s)
{
    BYTE obj[OBJ_READ_SIZE];
    DWORD ox, oy, cw, ch;
    int i;

    if (!IsWindow(g->hwnd))
        return 0;
    if (!rpm(g->process, g->obj, obj, sizeof(obj)))
        return 0;
    {
        DWORD vt;
        memcpy(&vt, obj, 4);
        if (vt != SISEN_VTABLE || !board_looks_valid(obj))
            return 0;
    }
    for (i = 0; i < SS_CELLS; i++) {
        int id;
        memcpy(&id, obj + OFF_BOARD + i * 4, 4);
        s->board[i] = id < 0 ? -1 : obj[OFF_KIND + id];
    }
    memcpy(&s->state, obj + OFF_STATE, 4);
    memcpy(&s->sel_col, obj + OFF_SEL_COL, 4);
    memcpy(&s->sel_row, obj + OFF_SEL_ROW, 4);
    memcpy(&s->assisted, obj + OFF_ASSISTED, 4);
    if (!rpm_dword(g->process, SISEN_G_ORIGIN_X, &ox) || !rpm_dword(g->process, SISEN_G_ORIGIN_Y, &oy) ||
        !rpm_dword(g->process, SISEN_G_CELL_W, &cw) || !rpm_dword(g->process, SISEN_G_CELL_H, &ch))
        return 0;
    s->ox = (int)ox; s->oy = (int)oy; s->cw = (int)cw; s->ch = (int)ch;
    if (s->cw <= 0 || s->ch <= 0 || s->cw > 1000 || s->ch > 1000)
        return 0;
    return 1;
}

static int mark_assisted(game_t *g)
{
    DWORD one = 1;
    SIZE_T done = 0;
    return WriteProcessMemory(g->process, (LPVOID)(ULONG_PTR)(g->obj + OFF_ASSISTED),
                              &one, sizeof(one), &done) && done == sizeof(one);
}

static void click_cell(game_t *g, const snapshot_t *s, int cell)
{
    int col = cell % SS_COLS, row = cell / SS_COLS;
    int x = s->ox + col * s->cw + s->cw / 2;
    int y = s->oy + row * s->ch + s->ch / 2;
    LPARAM lp = MAKELPARAM(x, y);
    PostMessageW(g->hwnd, WM_LBUTTONDOWN, MK_LBUTTON, lp);
    PostMessageW(g->hwnd, WM_LBUTTONUP, 0, lp);
}

/* ---- worker -------------------------------------------------------------------- */

#define WM_APP_STATUS (WM_APP + 1)  /* lParam: malloc'd wchar_t* */
#define WM_APP_DONE   (WM_APP + 2)

#define IDC_START   101
#define IDC_STOP    102
#define IDC_DELAY   103
#define IDC_STATUS  104
#define IDC_RETRY   105

static HWND g_main;
static volatile int g_cancel;
static HANDLE g_thread;
static int g_delay_ms = 120;
static int g_auto_retry = 1;

static void status(const wchar_t *fmt, ...)
{
    wchar_t *buf = malloc(512 * sizeof(wchar_t));
    va_list ap;
    if (!buf)
        return;
    va_start(ap, fmt);
    _vsnwprintf(buf, 511, fmt, ap);
    va_end(ap);
    buf[511] = 0;
    if (!PostMessageW(g_main, WM_APP_STATUS, 0, (LPARAM)buf))
        free(buf);
}

static void sleep_cancellable(int ms)
{
    while (ms > 0 && !g_cancel) {
        int step = ms > 20 ? 20 : ms;
        Sleep((DWORD)step);
        ms -= step;
    }
}

/* Waits until pred(snapshot) holds. Returns 1 on success, 0 on timeout/cancel/error. */
typedef int (*snap_pred)(const snapshot_t *, int);
static int wait_for(game_t *g, snapshot_t *s, snap_pred pred, int arg, int timeout_ms)
{
    DWORD start = GetTickCount();
    for (;;) {
        if (g_cancel || !read_snapshot(g, s))
            return 0;
        if (pred(s, arg))
            return 1;
        if ((int)(GetTickCount() - start) > timeout_ms)
            return 0;
        Sleep(10);
    }
}

static int pred_selected(const snapshot_t *s, int cell)
{
    return s->state == ST_SELECTED && s->sel_row * SS_COLS + s->sel_col == cell;
}
static int pred_removed(const snapshot_t *s, int cell)
{
    return s->board[cell] < 0 || s->state == ST_REMOVING;
}

static int count_tiles(const int *board)
{
    int i, n = 0;
    for (i = 0; i < SS_CELLS; i++)
        n += board[i] >= 0;
    return n;
}

/* Brings the game to the idle state (no selection, no removal animation running). */
static int ensure_idle(game_t *g, snapshot_t *s)
{
    int tries;
    for (tries = 0; tries < 50 && !g_cancel; tries++) {
        if (!read_snapshot(g, s))
            return 0;
        if (s->state == ST_IDLE)
            return 1;
        if (s->state == ST_SELECTED) {
            /* clicking the selected tile again cancels the selection */
            click_cell(g, s, s->sel_row * SS_COLS + s->sel_col);
        } else if (s->state == ST_REMOVING) {
            /* any click finishes the removal animation immediately */
            int i;
            for (i = 0; i < SS_CELLS && s->board[i] >= 0; i++)
                ;
            if (i < SS_CELLS)
                click_cell(g, s, i);
        }
        Sleep(60);
    }
    return 0;
}

static DWORD WINAPI worker(LPVOID unused)
{
    game_t g;
    snapshot_t s;
    int r, games = 0;
    (void)unused;

    r = find_game(&g);
    if (r < 0) {
        status(L"四川省 for Win을 찾았지만 지원하지 않는 버전입니다. 2.13 버전에서만 동작합니다.");
        PostMessageW(g_main, WM_APP_DONE, 0, 0);
        return 0;
    }
    if (r == 0) {
        status(L"게임 창을 찾지 못했습니다. Sisen.exe 2.13을 먼저 실행해 주세요. "
               L"(다른 버전이면 인식되지 않습니다)");
        PostMessageW(g_main, WM_APP_DONE, 0, 0);
        return 0;
    }

    for (;;) {
        ss_result *res;
        int k, left;

        if (!ensure_idle(&g, &s)) {
            if (!g_cancel)
                status(L"게임이 응답하지 않습니다. 메시지 창이 떠 있으면 닫고 다시 시도해 주세요.");
            break;
        }
        left = count_tiles(s.board);
        if (left == 0) {
            status(L"이미 모든 패가 제거되어 있습니다. F2로 새 게임을 시작한 뒤 다시 눌러 주세요.");
            break;
        }
        /* Same flag the game sets for Search/Undo: this game is not saved to the ranking. */
        if (!s.assisted && !mark_assisted(&g)) {
            status(L"랭킹 제외 플래그를 쓸 수 없어 중단합니다. (권한 문제일 수 있습니다)");
            break;
        }

        status(L"풀이 계산 중... (남은 패 %d개)", left);
        res = malloc(sizeof(*res));
        if (!res)
            break;
        ss_solve(s.board, 0, 20000, &g_cancel, res);
        if (g_cancel) {
            free(res);
            break;
        }
        if (!res->solved) {
            if (g_auto_retry && left == SS_CELLS && games < 50) {
                games++;
                status(L"이 배치는 끝까지 풀 수 없습니다. 새 게임을 시작합니다... (%d회째)", games);
                free(res);
                PostMessageW(g.hwnd, WM_COMMAND, MAKEWPARAM(CMD_GAME_START, 0), 0);
                sleep_cancellable(400);
                if (g_cancel)
                    break;
                continue;
            }
            status(L"끝까지 푸는 방법이 없습니다. 가능한 %d쌍만 제거합니다.", res->count);
        } else {
            status(L"풀이를 찾았습니다 (%d쌍). 진행 중...", res->count);
        }

        for (k = 0; k < res->count && !g_cancel; k++) {
            int a = res->moves[k].a, b = res->moves[k].b;

            if (!ensure_idle(&g, &s))
                break;
            if (s.board[a] < 0 || s.board[a] != s.board[b] || !ss_can_connect(s.board, a, b))
                break; /* board changed under us (the player clicked); solve again */

            click_cell(&g, &s, a);
            if (!wait_for(&g, &s, pred_selected, a, 2000))
                break;
            sleep_cancellable(g_delay_ms / 2);
            click_cell(&g, &s, b);
            if (!wait_for(&g, &s, pred_removed, b, 2000))
                break;
            status(L"진행 중... %d / %d쌍", k + 1, res->count);
            sleep_cancellable(g_delay_ms);
        }

        if (g_cancel) {
            free(res);
            break;
        }
        if (k < res->count) {
            /* Something changed or timed out: re-read the board and solve again. */
            free(res);
            if (!read_snapshot(&g, &s)) {
                status(L"게임과의 연결이 끊어졌습니다.");
                break;
            }
            continue;
        }
        {
            int solved = res->solved;
            free(res);
            /*
             * No more clicks after the last removal: the game finishes the animation on its
             * own and then shows its own message box (congratulations / no more moves).
             */
            sleep_cancellable(300);
            read_snapshot(&g, &s);
            if (solved) {
                status(L"완료! 모든 패를 제거했습니다. (자동 풀이 게임은 랭킹에 기록되지 않습니다)");
            } else {
                status(L"더 이상 제거할 수 있는 패가 없습니다. 남은 패 %d개.", count_tiles(s.board));
            }
        }
        break;
    }

    if (g_cancel)
        status(L"중지했습니다.");
    close_game(&g);
    PostMessageW(g_main, WM_APP_DONE, 0, 0);
    return 0;
}

/* ---- UI ------------------------------------------------------------------------- */

static HWND g_btn_start, g_btn_stop, g_edit_delay, g_status, g_chk_retry;

static void set_running(int running)
{
    EnableWindow(g_btn_start, !running);
    EnableWindow(g_btn_stop, running);
    EnableWindow(g_edit_delay, !running);
    EnableWindow(g_chk_retry, !running);
}

static HWND make(const wchar_t *cls, const wchar_t *text, DWORD style, int x, int y, int w, int h,
                 HWND parent, int id, HFONT font)
{
    HWND c = CreateWindowExW(0, cls, text, WS_CHILD | WS_VISIBLE | style, x, y, w, h, parent,
                             (HMENU)(INT_PTR)id, GetModuleHandleW(NULL), NULL);
    SendMessageW(c, WM_SETFONT, (WPARAM)font, TRUE);
    return c;
}

static LRESULT CALLBACK wnd_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    switch (msg) {
    case WM_CREATE: {
        HFONT font = (HFONT)GetStockObject(DEFAULT_GUI_FONT);
        NONCLIENTMETRICSW ncm;
        ncm.cbSize = sizeof(ncm);
        if (SystemParametersInfoW(SPI_GETNONCLIENTMETRICS, sizeof(ncm), &ncm, 0))
            font = CreateFontIndirectW(&ncm.lfMessageFont);

        make(L"STATIC", L"사천성(四川省 for Win 2.13)을 실행한 상태에서 [자동 풀기]를 누르세요.",
             0, 12, 12, 400, 20, hwnd, 0, font);
        make(L"STATIC", L"클릭 간격(ms):", 0, 12, 44, 90, 20, hwnd, 0, font);
        g_edit_delay = make(L"EDIT", L"120", WS_BORDER | ES_NUMBER, 104, 41, 60, 22, hwnd,
                            IDC_DELAY, font);
        g_chk_retry = make(L"BUTTON", L"풀 수 없는 배치면 자동으로 새 게임", BS_AUTOCHECKBOX,
                           180, 42, 240, 20, hwnd, IDC_RETRY, font);
        SendMessageW(g_chk_retry, BM_SETCHECK, BST_CHECKED, 0);
        g_btn_start = make(L"BUTTON", L"자동 풀기", BS_DEFPUSHBUTTON, 12, 76, 120, 30, hwnd,
                           IDC_START, font);
        g_btn_stop = make(L"BUTTON", L"중지", 0, 140, 76, 80, 30, hwnd, IDC_STOP, font);
        g_status = make(L"STATIC", L"대기 중", SS_LEFT, 12, 118, 400, 40, hwnd, IDC_STATUS, font);
        set_running(0);
        return 0;
    }
    case WM_COMMAND:
        if (LOWORD(wp) == IDC_START && !g_thread) {
            wchar_t buf[16];
            GetWindowTextW(g_edit_delay, buf, 16);
            g_delay_ms = _wtoi(buf);
            if (g_delay_ms < 0)
                g_delay_ms = 0;
            if (g_delay_ms > 5000)
                g_delay_ms = 5000;
            g_auto_retry = SendMessageW(g_chk_retry, BM_GETCHECK, 0, 0) == BST_CHECKED;
            g_cancel = 0;
            g_thread = CreateThread(NULL, 1 << 20, worker, NULL, 0, NULL);
            if (g_thread)
                set_running(1);
            else
                SetWindowTextW(g_status, L"작업 스레드를 만들 수 없습니다.");
        } else if (LOWORD(wp) == IDC_STOP) {
            g_cancel = 1;
        }
        return 0;
    case WM_APP_STATUS:
        SetWindowTextW(g_status, (const wchar_t *)lp);
        free((void *)lp);
        return 0;
    case WM_APP_DONE:
        if (g_thread) {
            WaitForSingleObject(g_thread, INFINITE);
            CloseHandle(g_thread);
            g_thread = NULL;
        }
        set_running(0);
        return 0;
    case WM_CLOSE:
        g_cancel = 1;
        if (g_thread) {
            WaitForSingleObject(g_thread, 5000);
            CloseHandle(g_thread);
            g_thread = NULL;
        }
        DestroyWindow(hwnd);
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

int WINAPI wWinMain(HINSTANCE inst, HINSTANCE prev, PWSTR cmd, int show)
{
    WNDCLASSW wc;
    MSG m;
    RECT rc = { 0, 0, 430, 170 };
    DWORD style = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX;
    (void)prev; (void)cmd;

    memset(&wc, 0, sizeof(wc));
    wc.lpfnWndProc = wnd_proc;
    wc.hInstance = inst;
    wc.hCursor = LoadCursorW(NULL, (LPCWSTR)IDC_ARROW);
    wc.hIcon = LoadIconW(inst, MAKEINTRESOURCEW(1));
    wc.hbrBackground = (HBRUSH)(COLOR_BTNFACE + 1);
    wc.lpszClassName = L"SisenAutoSolver";
    RegisterClassW(&wc);

    AdjustWindowRect(&rc, style, FALSE);
    g_main = CreateWindowExW(WS_EX_TOPMOST, wc.lpszClassName, L"사천성 자동 풀이", style,
                             CW_USEDEFAULT, CW_USEDEFAULT, rc.right - rc.left, rc.bottom - rc.top,
                             NULL, NULL, inst, NULL);
    if (!g_main)
        return 1;
    ShowWindow(g_main, show);
    UpdateWindow(g_main);

    while (GetMessageW(&m, NULL, 0, 0) > 0) {
        if (!IsDialogMessageW(g_main, &m)) {
            TranslateMessage(&m);
            DispatchMessageW(&m);
        }
    }
    return (int)m.wParam;
}
