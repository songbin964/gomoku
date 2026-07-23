import os
import sys
import ctypes
import numpy as np

BOARD_SIZE = 15

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(__file__)
    return os.path.join(base_path, relative_path)

try:
    dll_path = get_resource_path('gomoku_ai.dll')
    ai_dll = ctypes.CDLL(dll_path)
    
    ai_dll.get_best_move.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    ai_dll.get_best_move.restype = None
    
    ai_dll.get_best_move_medium.argtypes = [ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)]
    ai_dll.get_best_move_medium.restype = None
    
    HAS_C_DLL = True
    print("C语言AI引擎加载成功！")
except Exception as e:
    print(f"C语言AI引擎加载失败，使用Numba回退: {e}")
    HAS_C_DLL = False
    try:
        from numba import njit
        
        SCORES = np.array([10, 100, 500, 5000, 10000, 50000, 1000000], dtype=np.int64)
        DIRECTIONS = np.array([[0, 1], [1, 0], [1, 1], [1, -1]], dtype=np.int32)
        MAX_CANDIDATES = 30
        MAX_THREATS = 20
        
        @njit(cache=True)
        def check_pattern(board, row, col, player, dx, dy):
            left_open = False
            right_open = False
            count = 1
            
            r, c = row + dx, col + dy
            while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r, c] == player:
                count += 1
                r += dx
                c += dy
            if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r, c] == 0:
                right_open = True
            
            r, c = row - dx, col - dy
            while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r, c] == player:
                count += 1
                r -= dx
                c -= dy
            if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r, c] == 0:
                left_open = True
            
            both_open = left_open and right_open
            
            if count >= 5:
                return 6
            elif count == 4:
                return 5 if both_open else 4
            elif count == 3:
                return 3 if both_open else 2
            elif count == 2:
                return 1 if both_open else 0
            
            return -1
        
        @njit(cache=True)
        def get_pattern_score(pattern):
            if pattern >= 0 and pattern < len(SCORES):
                return SCORES[pattern]
            return 0
        
        @njit(cache=True)
        def evaluate_position(board, row, col, player):
            score = 0
            opponent = 1 if player == 2 else 2
            
            center = BOARD_SIZE // 2
            dist = abs(row - center) + abs(col - center)
            score += (BOARD_SIZE - dist) * 2
            
            board[row, col] = player
            
            for d in range(4):
                dx = DIRECTIONS[d, 0]
                dy = DIRECTIONS[d, 1]
                
                pattern = check_pattern(board, row, col, player, dx, dy)
                if pattern >= 0:
                    score += get_pattern_score(pattern)
                
                opp_pattern = check_pattern(board, row, col, opponent, dx, dy)
                if opp_pattern >= 0:
                    score -= get_pattern_score(opp_pattern) * 0.8
            
            board[row, col] = 0
            
            return score
        
        @njit(cache=True)
        def threat_scan(board, player, threats):
            opponent = 1 if player == 2 else 2
            threat_count = 0
            
            directions = ((0, 1), (1, 0), (1, 1), (1, -1))
            
            for row in range(BOARD_SIZE):
                for col in range(BOARD_SIZE):
                    if board[row, col] == 0:
                        board[row, col] = opponent
                        for dx, dy in directions:
                            pattern = check_pattern(board, row, col, opponent, dx, dy)
                            if pattern in [5, 4, 3]:
                                if threat_count < MAX_THREATS:
                                    threats[threat_count, 0] = row
                                    threats[threat_count, 1] = col
                                    threat_count += 1
                                break
                        board[row, col] = 0
            
            return threat_count
        
        @njit(cache=True)
        def get_candidates(board, threats, threat_count, candidates):
            candidate_count = 0
            center = BOARD_SIZE // 2
            
            for row in range(BOARD_SIZE):
                for col in range(BOARD_SIZE):
                    if board[row, col] == 0:
                        is_threat = False
                        if threat_count > 0:
                            for t in range(threat_count):
                                if threats[t, 0] == row and threats[t, 1] == col:
                                    is_threat = True
                                    break
                        
                        if is_threat:
                            if candidate_count < MAX_CANDIDATES:
                                candidates[candidate_count, 0] = row
                                candidates[candidate_count, 1] = col
                                candidates[candidate_count, 2] = 1
                                candidate_count += 1
                        else:
                            neighbor_count = 0
                            for dr in [-1, 0, 1]:
                                for dc in [-1, 0, 1]:
                                    if dr == 0 and dc == 0:
                                        continue
                                    nr, nc = row + dr, col + dc
                                    if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board[nr, nc] != 0:
                                        neighbor_count += 1
                            
                            if neighbor_count > 0:
                                if candidate_count < MAX_CANDIDATES:
                                    dist = abs(row - center) + abs(col - center)
                                    candidates[candidate_count, 0] = row
                                    candidates[candidate_count, 1] = col
                                    candidates[candidate_count, 2] = -neighbor_count * 100 - dist
                                    candidate_count += 1
            
            if candidate_count == 0:
                candidates[0, 0] = center
                candidates[0, 1] = center
                candidates[0, 2] = 0
                return 1
            
            for i in range(candidate_count):
                for j in range(i + 1, candidate_count):
                    if candidates[j, 2] > candidates[i, 2]:
                        tmp = candidates[i].copy()
                        candidates[i] = candidates[j]
                        candidates[j] = tmp
            
            return candidate_count
        
        @njit(cache=True)
        def minimax(board, depth, alpha, beta, player, ai_player, threats, threat_count):
            if depth == 0:
                score = 0
                candidates = np.zeros((MAX_CANDIDATES, 3), dtype=np.int32)
                cand_count = get_candidates(board, threats, threat_count, candidates)
                
                for i in range(cand_count):
                    row = candidates[i, 0]
                    col = candidates[i, 1]
                    score += evaluate_position(board, row, col, ai_player)
                
                return score
            
            candidates = np.zeros((MAX_CANDIDATES, 3), dtype=np.int32)
            cand_count = get_candidates(board, threats, threat_count, candidates)
            
            if player == ai_player:
                max_eval = -1000000000
                for i in range(cand_count):
                    row = candidates[i, 0]
                    col = candidates[i, 1]
                    
                    board[row, col] = player
                    eval = minimax(board, depth - 1, alpha, beta, 3 - player, ai_player, threats, threat_count)
                    board[row, col] = 0
                    
                    if eval > max_eval:
                        max_eval = eval
                    if eval > alpha:
                        alpha = eval
                    if beta <= alpha:
                        break
                
                return max_eval
            else:
                min_eval = 1000000000
                for i in range(cand_count):
                    row = candidates[i, 0]
                    col = candidates[i, 1]
                    
                    board[row, col] = player
                    eval = minimax(board, depth - 1, alpha, beta, 3 - player, ai_player, threats, threat_count)
                    board[row, col] = 0
                    
                    if eval < min_eval:
                        min_eval = eval
                    if eval < beta:
                        beta = eval
                    if beta <= alpha:
                        break
                
                return min_eval
        
        @njit(cache=True)
        def has_win(board, row, col, player):
            directions = ((0, 1), (1, 0), (1, 1), (1, -1))
            for dx, dy in directions:
                if check_pattern(board, row, col, player, dx, dy) == 6:
                    return True
            return False
        
        @njit(cache=True)
        def has_open_four(board, row, col, player):
            directions = ((0, 1), (1, 0), (1, 1), (1, -1))
            for dx, dy in directions:
                if check_pattern(board, row, col, player, dx, dy) == 5:
                    return True
            return False
        
        @njit(cache=True)
        def numba_get_best_move(board_np, depth=3):
            board = board_np.copy()
            
            move_count = np.count_nonzero(board)
            
            if move_count < 10:
                depth = 3
            elif move_count < 20:
                depth = 4
            else:
                depth = 5
            
            threats = np.zeros((MAX_THREATS, 2), dtype=np.int32)
            threat_count = threat_scan(board, 2, threats)
            
            candidates = np.zeros((MAX_CANDIDATES, 3), dtype=np.int32)
            cand_count = get_candidates(board, threats, threat_count, candidates)
            
            if cand_count == 0:
                return (-1, -1)
            
            if cand_count == 1:
                return (candidates[0, 0], candidates[0, 1])
            
            for i in range(cand_count):
                row = candidates[i, 0]
                col = candidates[i, 1]
                
                board[row, col] = 2
                if has_win(board, row, col, 2):
                    board[row, col] = 0
                    return (row, col)
                board[row, col] = 0
            
            for i in range(cand_count):
                row = candidates[i, 0]
                col = candidates[i, 1]
                
                board[row, col] = 1
                if has_win(board, row, col, 1):
                    board[row, col] = 0
                    return (row, col)
                board[row, col] = 0
            
            for i in range(cand_count):
                row = candidates[i, 0]
                col = candidates[i, 1]
                
                board[row, col] = 2
                if has_open_four(board, row, col, 2):
                    board[row, col] = 0
                    return (row, col)
                board[row, col] = 0
            
            for i in range(cand_count):
                row = candidates[i, 0]
                col = candidates[i, 1]
                
                board[row, col] = 1
                if has_open_four(board, row, col, 1):
                    board[row, col] = 0
                    return (row, col)
                board[row, col] = 0
            
            best_move = (-1, -1)
            best_score = -1000000000
            
            for i in range(cand_count):
                row = candidates[i, 0]
                col = candidates[i, 1]
                
                board[row, col] = 2
                score = minimax(board, depth, -1000000000, 1000000000, 1, 2, threats, threat_count)
                board[row, col] = 0
                
                if score > best_score:
                    best_score = score
                    best_move = (row, col)
            
            return best_move
    except:
        numba_get_best_move = None


def get_best_move(board_np, depth=3):
    if HAS_C_DLL:
        board_flat = board_np.flatten().astype(np.int32)
        board_ptr = board_flat.ctypes.data_as(ctypes.POINTER(ctypes.c_int))
        
        result = (ctypes.c_int * 2)()
        
        ai_dll.get_best_move(board_ptr, result)
        
        return (result[0], result[1])
    else:
        if numba_get_best_move:
            return numba_get_best_move(board_np, depth)
        return (-1, -1)


def get_best_move_medium(board_np, depth=3):
    if HAS_C_DLL:
        board_flat = board_np.flatten().astype(np.int32)
        board_ptr = board_flat.ctypes.data_as(ctypes.POINTER(ctypes.c_int))
        
        result = (ctypes.c_int * 2)()
        
        ai_dll.get_best_move_medium(board_ptr, result)
        
        return (result[0], result[1])
    else:
        if numba_get_best_move:
            return numba_get_best_move(board_np, 2)
        return (-1, -1)