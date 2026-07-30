#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <time.h>

#define BOARD_SIZE 15
#define MAX_CANDIDATES 50
#define WIN_SCORE 1000000000LL
#define TABLE_SIZE 131072

#define EMPTY 0
#define BLACK 1
#define WHITE 2

static int g_board[BOARD_SIZE][BOARD_SIZE];
static int g_candidates[MAX_CANDIDATES][3];

static unsigned long long g_hash_table[TABLE_SIZE];
static long long g_score_table[TABLE_SIZE];
static int g_depth_table[TABLE_SIZE];
static int g_hash_flags[TABLE_SIZE];

static int g_best_row, g_best_col;
static clock_t g_start_time;
static int g_time_limit_ms;
static int g_move_count;

static const int DIRECTIONS[4][2] = {{0, 1}, {1, 0}, {1, 1}, {1, -1}};

static inline int BOARD(int row, int col) {
    return g_board[row][col];
}

static inline void SET_BOARD(int row, int col, int val) {
    g_board[row][col] = val;
}

static unsigned long long hash_board() {
    unsigned long long hash = 17;
    for (int i = 0; i < BOARD_SIZE; i++) {
        for (int j = 0; j < BOARD_SIZE; j++) {
            hash = hash * 31 + g_board[i][j];
        }
    }
    return hash;
}

static int get_hash_entry(unsigned long long hash, long long *score, int *depth) {
    int idx = hash % TABLE_SIZE;
    if (g_hash_table[idx] == hash && g_hash_flags[idx]) {
        *score = g_score_table[idx];
        *depth = g_depth_table[idx];
        return 1;
    }
    return 0;
}

static void set_hash_entry(unsigned long long hash, long long score, int depth) {
    int idx = hash % TABLE_SIZE;
    g_hash_table[idx] = hash;
    g_score_table[idx] = score;
    g_depth_table[idx] = depth;
    g_hash_flags[idx] = 1;
}

static int is_timeout() {
    clock_t now = clock();
    double elapsed_ms = (double)(now - g_start_time) * 1000.0 / CLOCKS_PER_SEC;
    return elapsed_ms >= g_time_limit_ms;
}

static int count_in_dir(int player, int row, int col, int dx, int dy) {
    int count = 0;
    int r = row + dx;
    int c = col + dy;
    while (r >= 0 && r < BOARD_SIZE && c >= 0 && c < BOARD_SIZE && g_board[r][c] == player) {
        count++;
        r += dx;
        c += dy;
    }
    return count;
}

static int is_open_pos(int row, int col) {
    return row >= 0 && row < BOARD_SIZE && col >= 0 && col < BOARD_SIZE && g_board[row][col] == EMPTY;
}

static long long evaluate_single_line(const char *line, int len) {
    long long score = 0;
    int i = 0;
    
    while (i < len) {
        if (line[i] != '_') {
            char player = line[i];
            int start = i;
            
            while (i < len && line[i] == player) {
                i++;
            }
            
            int end = i - 1;
            int count = end - start + 1;
            
            int left_open = (start > 0 && line[start - 1] == '_');
            int right_open = (end < len - 1 && line[end + 1] == '_');
            
            if (count >= 5) {
                if (player == 'O') score += 10000000;
                else score -= 11000000;
            } else if (count == 4) {
                if (left_open && right_open) {
                    if (player == 'O') score += 5000000;
                    else score -= 5500000;
                } else if (left_open || right_open) {
                    if (player == 'O') score += 1000000;
                    else score -= 1100000;
                }
            } else if (count == 3) {
                if (left_open && right_open) {
                    if (player == 'O') score += 500000;
                    else score -= 550000;
                } else if (left_open || right_open) {
                    if (player == 'O') score += 50000;
                    else score -= 55000;
                }
            } else if (count == 2) {
                if (left_open && right_open) {
                    if (player == 'O') score += 50000;
                    else score -= 55000;
                } else if (left_open || right_open) {
                    if (player == 'O') score += 5000;
                    else score -= 5500;
                }
            } else if (count == 1) {
                if (left_open && right_open) {
                    if (player == 'O') score += 5000;
                    else score -= 5500;
                }
            }
            
            if (count == 3 && (left_open || right_open)) {
                if (start > 1 && line[start - 2] == player && line[start - 1] == '_') {
                    if (player == 'O') score += 800000;
                    else score -= 880000;
                }
                if (end < len - 2 && line[end + 2] == player && line[end + 1] == '_') {
                    if (player == 'O') score += 800000;
                    else score -= 880000;
                }
            }
            
            if (count == 2) {
                if (start > 1 && line[start - 2] == player && line[start - 1] == '_') {
                    if (player == 'O') score += 300000;
                    else score -= 330000;
                }
                if (end < len - 2 && line[end + 2] == player && line[end + 1] == '_') {
                    if (player == 'O') score += 300000;
                    else score -= 330000;
                }
                
                if (start > 2 && line[start - 3] == player && line[start - 2] == '_' && line[start - 1] == '_') {
                    if (player == 'O') score += 150000;
                    else score -= 165000;
                }
                if (end < len - 3 && line[end + 3] == player && line[end + 2] == '_' && line[end + 1] == '_') {
                    if (player == 'O') score += 150000;
                    else score -= 165000;
                }
            }
            
            if (count == 4 && (left_open || right_open)) {
                if (start > 1 && line[start - 2] == player && line[start - 1] == '_') {
                    if (player == 'O') score += 800000;
                    else score -= 880000;
                }
                if (end < len - 2 && line[end + 2] == player && line[end + 1] == '_') {
                    if (player == 'O') score += 800000;
                    else score -= 880000;
                }
            }
            
            if (count == 2) {
                if (start > 2 && line[start - 3] == player && line[start - 2] == player && line[start - 1] == '_') {
                    if (player == 'O') score += 800000;
                    else score -= 880000;
                }
                if (end < len - 3 && line[end + 3] == player && line[end + 2] == player && line[end + 1] == '_') {
                    if (player == 'O') score += 800000;
                    else score -= 880000;
                }
            }
        } else {
            i++;
        }
    }
    
    return score;
}

static long long evaluate_board() {
    long long score = 0;
    char line[BOARD_SIZE + 2];
    
    for (int i = 0; i < BOARD_SIZE; i++) {
        for (int j = 0; j < BOARD_SIZE; j++) {
            if (g_board[i][j] == WHITE) line[j] = 'O';
            else if (g_board[i][j] == BLACK) line[j] = 'X';
            else line[j] = '_';
        }
        line[BOARD_SIZE] = '\0';
        score += evaluate_single_line(line, BOARD_SIZE);
    }
    
    for (int j = 0; j < BOARD_SIZE; j++) {
        for (int i = 0; i < BOARD_SIZE; i++) {
            if (g_board[i][j] == WHITE) line[i] = 'O';
            else if (g_board[i][j] == BLACK) line[i] = 'X';
            else line[i] = '_';
        }
        line[BOARD_SIZE] = '\0';
        score += evaluate_single_line(line, BOARD_SIZE);
    }
    
    for (int start = 0; start <= 2 * (BOARD_SIZE - 1); start++) {
        int len = 0;
        for (int i = 0; i < BOARD_SIZE; i++) {
            int j = start - i;
            if (j >= 0 && j < BOARD_SIZE) {
                if (g_board[i][j] == WHITE) line[len++] = 'O';
                else if (g_board[i][j] == BLACK) line[len++] = 'X';
                else line[len++] = '_';
            }
        }
        line[len] = '\0';
        score += evaluate_single_line(line, len);
    }
    
    for (int start = -(BOARD_SIZE - 1); start < BOARD_SIZE; start++) {
        int len = 0;
        for (int i = 0; i < BOARD_SIZE; i++) {
            int j = i + start;
            if (j >= 0 && j < BOARD_SIZE) {
                if (g_board[i][j] == WHITE) line[len++] = 'O';
                else if (g_board[i][j] == BLACK) line[len++] = 'X';
                else line[len++] = '_';
            }
        }
        line[len] = '\0';
        score += evaluate_single_line(line, len);
    }
    
    return score;
}

static int check_win(int player) {
    for (int i = 0; i < BOARD_SIZE; i++) {
        for (int j = 0; j < BOARD_SIZE; j++) {
            if (g_board[i][j] == player) {
                for (int d = 0; d < 4; d++) {
                    int left = count_in_dir(player, i, j, -DIRECTIONS[d][0], -DIRECTIONS[d][1]);
                    int right = count_in_dir(player, i, j, DIRECTIONS[d][0], DIRECTIONS[d][1]);
                    if (left + right + 1 >= 5) {
                        return 1;
                    }
                }
            }
        }
    }
    return 0;
}

static int find_block_position(int player, int *block_row, int *block_col) {
    int block_r, block_c;
    
    for (int i = 0; i < BOARD_SIZE; i++) {
        for (int j = 0; j < BOARD_SIZE; j++) {
            if (g_board[i][j] == player) {
                for (int d = 0; d < 4; d++) {
                    int left = count_in_dir(player, i, j, -DIRECTIONS[d][0], -DIRECTIONS[d][1]);
                    int right = count_in_dir(player, i, j, DIRECTIONS[d][0], DIRECTIONS[d][1]);
                    int total = left + right + 1;
                    
                    if (total >= 4) {
                        block_r = i - DIRECTIONS[d][0] * (left + 1);
                        block_c = j - DIRECTIONS[d][1] * (left + 1);
                        if (is_open_pos(block_r, block_c)) {
                            *block_row = block_r;
                            *block_col = block_c;
                            return 1;
                        }
                        block_r = i + DIRECTIONS[d][0] * (right + 1);
                        block_c = j + DIRECTIONS[d][1] * (right + 1);
                        if (is_open_pos(block_r, block_c)) {
                            *block_row = block_r;
                            *block_col = block_c;
                            return 1;
                        }
                    }
                }
            }
        }
    }
    
    for (int i = 0; i < BOARD_SIZE; i++) {
        for (int j = 0; j < BOARD_SIZE; j++) {
            if (g_board[i][j] == player) {
                for (int d = 0; d < 4; d++) {
                    int left = count_in_dir(player, i, j, -DIRECTIONS[d][0], -DIRECTIONS[d][1]);
                    int right = count_in_dir(player, i, j, DIRECTIONS[d][0], DIRECTIONS[d][1]);
                    int total = left + right + 1;
                    
                    if (total == 3) {
                        int left_open = is_open_pos(i - DIRECTIONS[d][0] * (left + 1), j - DIRECTIONS[d][1] * (left + 1));
                        int right_open = is_open_pos(i + DIRECTIONS[d][0] * (right + 1), j + DIRECTIONS[d][1] * (right + 1));
                        
                        if (left_open && right_open) {
                            *block_row = i - DIRECTIONS[d][0] * (left + 1);
                            *block_col = j - DIRECTIONS[d][1] * (left + 1);
                            return 1;
                        }
                    }
                }
            }
        }
    }
    
    for (int i = 0; i < BOARD_SIZE; i++) {
        for (int j = 0; j < BOARD_SIZE; j++) {
            if (g_board[i][j] == player) {
                for (int d = 0; d < 4; d++) {
                    int left = count_in_dir(player, i, j, -DIRECTIONS[d][0], -DIRECTIONS[d][1]);
                    int right = count_in_dir(player, i, j, DIRECTIONS[d][0], DIRECTIONS[d][1]);
                    int total = left + right + 1;
                    
                    if (total == 3) {
                        int left_open = is_open_pos(i - DIRECTIONS[d][0] * (left + 1), j - DIRECTIONS[d][1] * (left + 1));
                        int right_open = is_open_pos(i + DIRECTIONS[d][0] * (right + 1), j + DIRECTIONS[d][1] * (right + 1));
                        
                        if (left_open || right_open) {
                            if (left_open) {
                                *block_row = i - DIRECTIONS[d][0] * (left + 1);
                                *block_col = j - DIRECTIONS[d][1] * (left + 1);
                                return 1;
                            }
                            if (right_open) {
                                *block_row = i + DIRECTIONS[d][0] * (right + 1);
                                *block_col = j + DIRECTIONS[d][1] * (right + 1);
                                return 1;
                            }
                        }
                    }
                }
            }
        }
    }
    
    for (int i = 0; i < BOARD_SIZE; i++) {
        for (int j = 0; j < BOARD_SIZE; j++) {
            if (g_board[i][j] == player) {
                for (int d = 0; d < 4; d++) {
                    int left = count_in_dir(player, i, j, -DIRECTIONS[d][0], -DIRECTIONS[d][1]);
                    int right = count_in_dir(player, i, j, DIRECTIONS[d][0], DIRECTIONS[d][1]);
                    int total = left + right + 1;
                    
                    if (total == 3) {
                        int jump_found = 0;
                        int jump_block_r = -1, jump_block_c = -1;
                        
                        if (right >= 2 && 
                            i + DIRECTIONS[d][0] * (right + 1) >= 0 && 
                            i + DIRECTIONS[d][0] * (right + 1) < BOARD_SIZE &&
                            j + DIRECTIONS[d][1] * (right + 1) >= 0 && 
                            j + DIRECTIONS[d][1] * (right + 1) < BOARD_SIZE &&
                            g_board[i + DIRECTIONS[d][0] * (right + 1)][j + DIRECTIONS[d][1] * (right + 1)] == player &&
                            is_open_pos(i + DIRECTIONS[d][0] * (right + 1), j + DIRECTIONS[d][1] * (right + 1))) {
                            jump_found = 1;
                            jump_block_r = i + DIRECTIONS[d][0] * (right + 1);
                            jump_block_c = j + DIRECTIONS[d][1] * (right + 1);
                        }
                        if (left >= 2 &&
                            i - DIRECTIONS[d][0] * (left + 1) >= 0 && 
                            i - DIRECTIONS[d][0] * (left + 1) < BOARD_SIZE &&
                            j - DIRECTIONS[d][1] * (left + 1) >= 0 && 
                            j - DIRECTIONS[d][1] * (left + 1) < BOARD_SIZE &&
                            g_board[i - DIRECTIONS[d][0] * (left + 1)][j - DIRECTIONS[d][1] * (left + 1)] == player &&
                            is_open_pos(i - DIRECTIONS[d][0] * (left + 1), j - DIRECTIONS[d][1] * (left + 1))) {
                            jump_found = 1;
                            jump_block_r = i - DIRECTIONS[d][0] * (left + 1);
                            jump_block_c = j - DIRECTIONS[d][1] * (left + 1);
                        }
                        if (jump_found) {
                            *block_row = jump_block_r;
                            *block_col = jump_block_c;
                            return 1;
                        }
                    }
                }
            }
        }
    }
    
    return 0;
}

static int vcf_search(int player, int depth) {
    if (depth == 0) return 0;
    
    for (int i = 0; i < BOARD_SIZE; i++) {
        for (int j = 0; j < BOARD_SIZE; j++) {
            if (g_board[i][j] == EMPTY) {
                SET_BOARD(i, j, player);
                
                if (check_win(player)) {
                    SET_BOARD(i, j, EMPTY);
                    return 1;
                }
                
                int has_four = 0;
                for (int d = 0; d < 4; d++) {
                    int left = count_in_dir(player, i, j, -DIRECTIONS[d][0], -DIRECTIONS[d][1]);
                    int right = count_in_dir(player, i, j, DIRECTIONS[d][0], DIRECTIONS[d][1]);
                    if (left + right + 1 >= 4) {
                        has_four = 1;
                        break;
                    }
                }
                
                if (has_four) {
                    int opponent_can_win = 0;
                    for (int ii = 0; ii < BOARD_SIZE && !opponent_can_win; ii++) {
                        for (int jj = 0; jj < BOARD_SIZE && !opponent_can_win; jj++) {
                            if (g_board[ii][jj] == EMPTY) {
                                SET_BOARD(ii, jj, 3 - player);
                                if (check_win(3 - player)) {
                                    opponent_can_win = 1;
                                }
                                SET_BOARD(ii, jj, EMPTY);
                            }
                        }
                    }
                    
                    if (!opponent_can_win) {
                        int opponent_defended = 0;
                        for (int ii = 0; ii < BOARD_SIZE && !opponent_defended; ii++) {
                            for (int jj = 0; jj < BOARD_SIZE && !opponent_defended; jj++) {
                                if (g_board[ii][jj] == EMPTY) {
                                    SET_BOARD(ii, jj, 3 - player);
                                    int still_four = 0;
                                    for (int d = 0; d < 4; d++) {
                                        int left = count_in_dir(player, i, j, -DIRECTIONS[d][0], -DIRECTIONS[d][1]);
                                        int right = count_in_dir(player, i, j, DIRECTIONS[d][0], DIRECTIONS[d][1]);
                                        if (left + right + 1 >= 4) {
                                            still_four = 1;
                                            break;
                                        }
                                    }
                                    if (!still_four) {
                                        opponent_defended = 1;
                                        if (vcf_search(player, depth - 1)) {
                                            SET_BOARD(ii, jj, EMPTY);
                                            SET_BOARD(i, j, EMPTY);
                                            return 1;
                                        }
                                    }
                                    SET_BOARD(ii, jj, EMPTY);
                                }
                            }
                        }
                        
                        if (!opponent_defended) {
                            SET_BOARD(i, j, EMPTY);
                            return 1;
                        }
                    }
                }
                
                SET_BOARD(i, j, EMPTY);
            }
        }
    }
    
    return 0;
}

static int find_vcf_move(int player, int *result_row, int *result_col) {
    for (int i = 0; i < BOARD_SIZE; i++) {
        for (int j = 0; j < BOARD_SIZE; j++) {
            if (g_board[i][j] == EMPTY) {
                SET_BOARD(i, j, player);
                
                if (check_win(player)) {
                    SET_BOARD(i, j, EMPTY);
                    *result_row = i;
                    *result_col = j;
                    return 1;
                }
                
                int has_four = 0;
                for (int d = 0; d < 4; d++) {
                    int left = count_in_dir(player, i, j, -DIRECTIONS[d][0], -DIRECTIONS[d][1]);
                    int right = count_in_dir(player, i, j, DIRECTIONS[d][0], DIRECTIONS[d][1]);
                    if (left + right + 1 >= 4) {
                        has_four = 1;
                        break;
                    }
                }
                
                if (has_four) {
                    int opponent_can_win = 0;
                    for (int ii = 0; ii < BOARD_SIZE && !opponent_can_win; ii++) {
                        for (int jj = 0; jj < BOARD_SIZE && !opponent_can_win; jj++) {
                            if (g_board[ii][jj] == EMPTY) {
                                SET_BOARD(ii, jj, 3 - player);
                                if (check_win(3 - player)) {
                                    opponent_can_win = 1;
                                }
                                SET_BOARD(ii, jj, EMPTY);
                            }
                        }
                    }
                    
                    if (!opponent_can_win) {
                        if (vcf_search(player, 4)) {
                            SET_BOARD(i, j, EMPTY);
                            *result_row = i;
                            *result_col = j;
                            return 1;
                        }
                    }
                }
                
                SET_BOARD(i, j, EMPTY);
            }
        }
    }
    
    return 0;
}

static int evaluate_position_for_candidate(int row, int col, int player) {
    int score = 0;
    int center = BOARD_SIZE / 2;
    int dist = abs(row - center) + abs(col - center);
    score += (BOARD_SIZE - dist) * 10;
    
    SET_BOARD(row, col, player);
    
    if (check_win(player)) {
        SET_BOARD(row, col, EMPTY);
        return 10000000;
    }
    
    for (int d = 0; d < 4; d++) {
        int left = count_in_dir(player, row, col, -DIRECTIONS[d][0], -DIRECTIONS[d][1]);
        int right = count_in_dir(player, row, col, DIRECTIONS[d][0], DIRECTIONS[d][1]);
        int left_open = is_open_pos(row - DIRECTIONS[d][0] * (left + 1), col - DIRECTIONS[d][1] * (left + 1));
        int right_open = is_open_pos(row + DIRECTIONS[d][0] * (right + 1), col + DIRECTIONS[d][1] * (right + 1));
        
        if (left + right + 1 >= 5) score += 10000000;
        else if (left + right + 1 >= 4) {
            if (left_open && right_open) score += 5000000;
            else if (left_open || right_open) score += 1000000;
        } else if (left + right + 1 == 3) {
            if (left_open && right_open) score += 500000;
            else if (left_open || right_open) score += 50000;
        } else if (left + right + 1 == 2) {
            if (left_open && right_open) score += 50000;
        }
        
        int jump_score = 0;
        for (int k = 1; k <= 2; k++) {
            int nr = row + DIRECTIONS[d][0] * (right + k);
            int nc = col + DIRECTIONS[d][1] * (right + k);
            if (nr >= 0 && nr < BOARD_SIZE && nc >= 0 && nc < BOARD_SIZE && g_board[nr][nc] == player) {
                jump_score += 300000;
            }
        }
        for (int k = 1; k <= 2; k++) {
            int nr = row - DIRECTIONS[d][0] * (left + k);
            int nc = col - DIRECTIONS[d][1] * (left + k);
            if (nr >= 0 && nr < BOARD_SIZE && nc >= 0 && nc < BOARD_SIZE && g_board[nr][nc] == player) {
                jump_score += 300000;
            }
        }
        score += jump_score;
    }
    
    int opponent = (player == BLACK) ? WHITE : BLACK;
    for (int d = 0; d < 4; d++) {
        int left = count_in_dir(opponent, row, col, -DIRECTIONS[d][0], -DIRECTIONS[d][1]);
        int right = count_in_dir(opponent, row, col, DIRECTIONS[d][0], DIRECTIONS[d][1]);
        int left_open = is_open_pos(row - DIRECTIONS[d][0] * (left + 1), col - DIRECTIONS[d][1] * (left + 1));
        int right_open = is_open_pos(row + DIRECTIONS[d][0] * (right + 1), col + DIRECTIONS[d][1] * (right + 1));
        
        if (left + right + 1 >= 5) score += 11000000;
        else if (left + right + 1 >= 4) {
            if (left_open && right_open) score += 6000000;
            else if (left_open || right_open) score += 1500000;
        } else if (left + right + 1 == 3) {
            if (left_open && right_open) score += 600000;
            else if (left_open || right_open) score += 80000;
        } else if (left + right + 1 == 2) {
            if (left_open && right_open) score += 80000;
        }
        
        int opp_jump_score = 0;
        for (int k = 1; k <= 2; k++) {
            int nr = row + DIRECTIONS[d][0] * (right + k);
            int nc = col + DIRECTIONS[d][1] * (right + k);
            if (nr >= 0 && nr < BOARD_SIZE && nc >= 0 && nc < BOARD_SIZE && g_board[nr][nc] == opponent) {
                opp_jump_score += 400000;
            }
        }
        for (int k = 1; k <= 2; k++) {
            int nr = row - DIRECTIONS[d][0] * (left + k);
            int nc = col - DIRECTIONS[d][1] * (left + k);
            if (nr >= 0 && nr < BOARD_SIZE && nc >= 0 && nc < BOARD_SIZE && g_board[nr][nc] == opponent) {
                opp_jump_score += 400000;
            }
        }
        score += opp_jump_score;
    }
    
    SET_BOARD(row, col, EMPTY);
    
    return score;
}

static int get_candidates(int player) {
    int candidate_count = 0;
    
    for (int row = 0; row < BOARD_SIZE; row++) {
        for (int col = 0; col < BOARD_SIZE; col++) {
            if (g_board[row][col] == EMPTY) {
                int neighbor_count = 0;
                for (int dr = -2; dr <= 2; dr++) {
                    for (int dc = -2; dc <= 2; dc++) {
                        if (dr == 0 && dc == 0) continue;
                        int nr = row + dr;
                        int nc = col + dc;
                        if (nr >= 0 && nr < BOARD_SIZE && nc >= 0 && nc < BOARD_SIZE && g_board[nr][nc] != EMPTY) {
                            neighbor_count++;
                        }
                    }
                }
                
                if (neighbor_count > 0) {
                    if (candidate_count < MAX_CANDIDATES) {
                        g_candidates[candidate_count][0] = row;
                        g_candidates[candidate_count][1] = col;
                        g_candidates[candidate_count][2] = evaluate_position_for_candidate(row, col, player);
                        candidate_count++;
                    }
                }
            }
        }
    }
    
    if (candidate_count == 0) {
        int center = BOARD_SIZE / 2;
        g_candidates[0][0] = center;
        g_candidates[0][1] = center;
        g_candidates[0][2] = 0;
        return 1;
    }
    
    for (int i = 0; i < candidate_count - 1; i++) {
        for (int j = i + 1; j < candidate_count; j++) {
            if (g_candidates[j][2] > g_candidates[i][2]) {
                int tmp[3];
                memcpy(tmp, g_candidates[i], sizeof(tmp));
                memcpy(g_candidates[i], g_candidates[j], sizeof(tmp));
                memcpy(g_candidates[j], tmp, sizeof(tmp));
            }
        }
    }
    
    return candidate_count;
}

static long long minimax(int depth, long long alpha, long long beta, int player) {
    if (depth == 0 || is_timeout()) {
        return evaluate_board();
    }
    
    unsigned long long hash = hash_board();
    long long hash_score;
    int hash_depth;
    if (get_hash_entry(hash, &hash_score, &hash_depth)) {
        if (hash_depth >= depth) {
            return hash_score;
        }
    }
    
    int cand_count = get_candidates(player);
    
    long long best_score = (player == WHITE) ? LLONG_MIN : LLONG_MAX;
    
    for (int i = 0; i < cand_count && !is_timeout(); i++) {
        int row = g_candidates[i][0];
        int col = g_candidates[i][1];
        
        SET_BOARD(row, col, player);
        
        if (check_win(player)) {
            SET_BOARD(row, col, EMPTY);
            set_hash_entry(hash, (player == WHITE) ? WIN_SCORE : -WIN_SCORE, depth);
            return (player == WHITE) ? WIN_SCORE : -WIN_SCORE;
        }
        
        long long score = minimax(depth - 1, alpha, beta, 3 - player);
        
        SET_BOARD(row, col, EMPTY);
        
        if (player == WHITE) {
            if (score > best_score) best_score = score;
            if (score > alpha) alpha = score;
        } else {
            if (score < best_score) best_score = score;
            if (score < beta) beta = score;
        }
        
        if (beta <= alpha) break;
    }
    
    set_hash_entry(hash, best_score, depth);
    return best_score;
}

__declspec(dllexport) void get_best_move(int *board_np, int *result) {
    memset(g_hash_table, 0, sizeof(g_hash_table));
    memset(g_score_table, 0, sizeof(g_score_table));
    memset(g_depth_table, 0, sizeof(g_depth_table));
    memset(g_hash_flags, 0, sizeof(g_hash_flags));
    
    for (int i = 0; i < BOARD_SIZE; i++) {
        for (int j = 0; j < BOARD_SIZE; j++) {
            g_board[i][j] = board_np[i * BOARD_SIZE + j];
        }
    }
    
    g_move_count = 0;
    for (int i = 0; i < BOARD_SIZE * BOARD_SIZE; i++) {
        if (board_np[i] != 0) g_move_count++;
    }
    
    g_time_limit_ms = 20000;
    if (g_move_count < 8) g_time_limit_ms = 6000;
    else if (g_move_count < 15) g_time_limit_ms = 10000;
    else if (g_move_count < 25) g_time_limit_ms = 15000;
    
    g_start_time = clock();
    
    for (int row = 0; row < BOARD_SIZE; row++) {
        for (int col = 0; col < BOARD_SIZE; col++) {
            if (g_board[row][col] == EMPTY) {
                SET_BOARD(row, col, WHITE);
                if (check_win(WHITE)) {
                    SET_BOARD(row, col, EMPTY);
                    result[0] = row;
                    result[1] = col;
                    return;
                }
                SET_BOARD(row, col, EMPTY);
            }
        }
    }
    
    for (int row = 0; row < BOARD_SIZE; row++) {
        for (int col = 0; col < BOARD_SIZE; col++) {
            if (g_board[row][col] == EMPTY) {
                SET_BOARD(row, col, BLACK);
                if (check_win(BLACK)) {
                    SET_BOARD(row, col, EMPTY);
                    result[0] = row;
                    result[1] = col;
                    return;
                }
                SET_BOARD(row, col, EMPTY);
            }
        }
    }
    
    int block_row, block_col;
    if (find_block_position(BLACK, &block_row, &block_col)) {
        result[0] = block_row;
        result[1] = block_col;
        return;
    }
    
    for (int row = 0; row < BOARD_SIZE; row++) {
        for (int col = 0; col < BOARD_SIZE; col++) {
            if (g_board[row][col] == EMPTY) {
                SET_BOARD(row, col, WHITE);
                int has_four = 0;
                for (int d = 0; d < 4; d++) {
                    int left = count_in_dir(WHITE, row, col, -DIRECTIONS[d][0], -DIRECTIONS[d][1]);
                    int right = count_in_dir(WHITE, row, col, DIRECTIONS[d][0], DIRECTIONS[d][1]);
                    if (left + right + 1 >= 4) {
                        has_four = 1;
                        break;
                    }
                }
                SET_BOARD(row, col, EMPTY);
                if (has_four) {
                    result[0] = row;
                    result[1] = col;
                    return;
                }
            }
        }
    }
    
    if (find_vcf_move(WHITE, &result[0], &result[1])) {
        return;
    }
    
    if (find_vcf_move(BLACK, &result[0], &result[1])) {
        return;
    }
    
    int cand_count = get_candidates(WHITE);
    
    if (cand_count == 0) {
        int center = BOARD_SIZE / 2;
        result[0] = center;
        result[1] = center;
        return;
    }
    
    g_best_row = g_candidates[0][0];
    g_best_col = g_candidates[0][1];
    long long best_score = LLONG_MIN;
    
    int max_depth = 6;
    if (g_move_count >= 3 && g_move_count < 10) max_depth = 7;
    else if (g_move_count >= 10 && g_move_count < 20) max_depth = 8;
    else if (g_move_count >= 20) max_depth = 10;
    
    for (int depth = 4; depth <= max_depth && !is_timeout(); depth++) {
        cand_count = get_candidates(WHITE);
        int eval_count = (cand_count > 12) ? 12 : cand_count;
        
        for (int i = 0; i < eval_count && !is_timeout(); i++) {
            int row = g_candidates[i][0];
            int col = g_candidates[i][1];
            
            SET_BOARD(row, col, WHITE);
            
            long long score = minimax(depth - 1, LLONG_MIN, LLONG_MAX, BLACK);
            
            SET_BOARD(row, col, EMPTY);
            
            if (score > best_score) {
                best_score = score;
                g_best_row = row;
                g_best_col = col;
            }
        }
    }
    
    result[0] = g_best_row;
    result[1] = g_best_col;
}

__declspec(dllexport) void get_best_move_medium(int *board_np, int *result) {
    for (int i = 0; i < BOARD_SIZE; i++) {
        for (int j = 0; j < BOARD_SIZE; j++) {
            g_board[i][j] = board_np[i * BOARD_SIZE + j];
        }
    }
    
    g_move_count = 0;
    for (int i = 0; i < BOARD_SIZE * BOARD_SIZE; i++) {
        if (board_np[i] != 0) g_move_count++;
    }
    
    g_time_limit_ms = 2000;
    g_start_time = clock();
    
    for (int row = 0; row < BOARD_SIZE; row++) {
        for (int col = 0; col < BOARD_SIZE; col++) {
            if (g_board[row][col] == EMPTY) {
                SET_BOARD(row, col, WHITE);
                if (check_win(WHITE)) {
                    SET_BOARD(row, col, EMPTY);
                    result[0] = row;
                    result[1] = col;
                    return;
                }
                SET_BOARD(row, col, EMPTY);
            }
        }
    }
    
    for (int row = 0; row < BOARD_SIZE; row++) {
        for (int col = 0; col < BOARD_SIZE; col++) {
            if (g_board[row][col] == EMPTY) {
                SET_BOARD(row, col, BLACK);
                if (check_win(BLACK)) {
                    SET_BOARD(row, col, EMPTY);
                    result[0] = row;
                    result[1] = col;
                    return;
                }
                SET_BOARD(row, col, EMPTY);
            }
        }
    }
    
    int cand_count = get_candidates(WHITE);
    
    if (cand_count == 0) {
        int center = BOARD_SIZE / 2;
        result[0] = center;
        result[1] = center;
        return;
    }
    
    g_best_row = g_candidates[0][0];
    g_best_col = g_candidates[0][1];
    long long best_score = LLONG_MIN;
    
    int max_depth = 2;
    if (g_move_count >= 10) max_depth = 3;
    if (g_move_count >= 20) max_depth = 4;
    
    for (int depth = 2; depth <= max_depth && !is_timeout(); depth++) {
        cand_count = get_candidates(WHITE);
        
        for (int i = 0; i < cand_count && !is_timeout(); i++) {
            int row = g_candidates[i][0];
            int col = g_candidates[i][1];
            
            SET_BOARD(row, col, WHITE);
            
            long long score = minimax(depth - 1, LLONG_MIN, LLONG_MAX, BLACK);
            
            SET_BOARD(row, col, EMPTY);
            
            if (score > best_score) {
                best_score = score;
                g_best_row = row;
                g_best_col = col;
            }
        }
    }
    
    result[0] = g_best_row;
    result[1] = g_best_col;
}