import pygame
import sys
import random
import os
import numpy as np
import json

try:
    from ai_engine import get_best_move, get_best_move_medium
    HAS_NUMBA = True
except Exception as e:
    print(f"Numba not available, using pure Python AI: {e}")
    HAS_NUMBA = False

EXPERIENCE_FILE = os.path.join(os.path.dirname(__file__), 'ai_experience.json')


def load_experience():
    try:
        if os.path.exists(EXPERIENCE_FILE):
            with open(EXPERIENCE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {'bad_moves': [], 'good_moves': [], 'learned_patterns': {}}


def save_experience(experience):
    try:
        with open(EXPERIENCE_FILE, 'w', encoding='utf-8') as f:
            json.dump(experience, f)
    except:
        pass


def board_to_key(board):
    return ''.join(str(board[r][c]) for r in range(BOARD_SIZE) for c in range(BOARD_SIZE))


def get_board_fingerprint(board, recent_moves=5):
    moves = []
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            if board[r][c] != 0:
                moves.append((r, c, board[r][c]))
    moves.sort(key=lambda x: x[2])
    recent = moves[-recent_moves:]
    return tuple(recent)

pygame.init()

SCREEN_WIDTH = 700
SCREEN_HEIGHT = 700
BOARD_SIZE = 15
CELL_SIZE = 40
MARGIN = 35

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BOARD_COLOR = (230, 180, 130)
RED = (255, 0, 0)
GRAY = (150, 150, 150)
BLUE = (0, 0, 255)
GREEN = (0, 200, 0)

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("五子棋")


def generate_sounds():
    sample_rate = 44100
    
    click_samples = np.sin(2 * np.pi * 800 * np.arange(sample_rate * 0.05) / sample_rate)
    click_samples = (click_samples * 32767).astype(np.int16)
    click_sound = pygame.mixer.Sound(click_samples)
    
    win_samples = []
    for freq in [523, 659, 784, 1047]:
        note = np.sin(2 * np.pi * freq * np.arange(sample_rate * 0.1) / sample_rate)
        note = (note * 32767 * 0.5).astype(np.int16)
        win_samples.append(note)
    win_samples = np.concatenate(win_samples)
    win_sound = pygame.mixer.Sound(win_samples)
    
    return click_sound, win_sound


try:
    click_sound, win_sound = generate_sounds()
except:
    click_sound = None
    win_sound = None


def play_sound(sound):
    if sound:
        try:
            sound.play()
        except:
            pass


class GameBoard:
    def __init__(self):
        self.board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.history = []
        self.current_player = 1
        self.game_over = False
        self.winner = None
        self.win_line = []

    def reset(self):
        self.board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        self.history = []
        self.current_player = 1
        self.game_over = False
        self.winner = None
        self.win_line = []

    def is_valid_move(self, row, col):
        return 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE and self.board[row][col] == 0

    def make_move(self, row, col):
        if not self.is_valid_move(row, col) or self.game_over:
            return False
        
        self.board[row][col] = self.current_player
        self.history.append((row, col, self.current_player))
        
        if self.check_win(row, col):
            self.game_over = True
            self.winner = self.current_player
            play_sound(win_sound)
        else:
            self.current_player = 2 if self.current_player == 1 else 1
        
        play_sound(click_sound)
        return True

    def undo(self, steps=1):
        for _ in range(steps):
            if not self.history:
                return False
            
            row, col, player = self.history.pop()
            self.board[row][col] = 0
        
        if self.history:
            self.current_player = self.history[-1][2]
        else:
            self.current_player = 1
        
        self.game_over = False
        self.winner = None
        self.win_line = []
        return True

    def check_win(self, row, col):
        directions = [
            (0, 1),
            (1, 0),
            (1, 1),
            (1, -1)
        ]
        
        for dx, dy in directions:
            line = [(row, col)]
            
            for i in range(1, 5):
                new_row, new_col = row + dx * i, col + dy * i
                if 0 <= new_row < BOARD_SIZE and 0 <= new_col < BOARD_SIZE and \
                   self.board[new_row][new_col] == self.current_player:
                    line.append((new_row, new_col))
                else:
                    break
            
            for i in range(1, 5):
                new_row, new_col = row - dx * i, col - dy * i
                if 0 <= new_row < BOARD_SIZE and 0 <= new_col < BOARD_SIZE and \
                   self.board[new_row][new_col] == self.current_player:
                    line.append((new_row, new_col))
                else:
                    break
            
            if len(line) >= 5:
                self.win_line = line
                return True
        
        return False


class WeakAI:
    def __init__(self):
        self.random_chance = 0.2
    
    def check_pattern(self, board, row, col, player, dx, dy):
        left_open = False
        right_open = False
        count = 1
        
        r, c = row + dx, col + dy
        while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == player:
            count += 1
            r += dx
            c += dy
        if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == 0:
            right_open = True
        
        r, c = row - dx, col - dy
        while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == player:
            count += 1
            r -= dx
            c -= dy
        if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == 0:
            left_open = True
        
        return count, left_open, right_open
    
    def has_win(self, board, row, col, player):
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        for dx, dy in directions:
            count, _, _ = self.check_pattern(board, row, col, player, dx, dy)
            if count >= 5:
                return True
        return False
    
    def has_four(self, board, row, col, player):
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        for dx, dy in directions:
            count, left_open, right_open = self.check_pattern(board, row, col, player, dx, dy)
            if count == 4 and (left_open or right_open):
                return True
        return False
    
    def has_three(self, board, row, col, player):
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        for dx, dy in directions:
            count, left_open, right_open = self.check_pattern(board, row, col, player, dx, dy)
            if count == 3 and (left_open and right_open):
                return True
        return False
    
    def get_move(self, board):
        valid_moves = []
        
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                if board[row][col] == 0:
                    valid_moves.append((row, col))
        
        if not valid_moves:
            return None
        
        for row, col in valid_moves:
            board[row][col] = 2
            if self.has_win(board, row, col, 2):
                board[row][col] = 0
                return (row, col)
            board[row][col] = 0
        
        for row, col in valid_moves:
            board[row][col] = 1
            if self.has_win(board, row, col, 1):
                board[row][col] = 0
                return (row, col)
            board[row][col] = 0
        
        for row, col in valid_moves:
            board[row][col] = 2
            if self.has_four(board, row, col, 2):
                board[row][col] = 0
                return (row, col)
            board[row][col] = 0
        
        for row, col in valid_moves:
            board[row][col] = 1
            if self.has_four(board, row, col, 1):
                board[row][col] = 0
                return (row, col)
            board[row][col] = 0
        
        candidates = []
        center = BOARD_SIZE // 2
        
        for row, col in valid_moves:
            board[row][col] = 2
            if self.has_three(board, row, col, 2):
                candidates.append((50, row, col))
            board[row][col] = 0
        
        for row, col in valid_moves:
            board[row][col] = 1
            if self.has_three(board, row, col, 1):
                candidates.append((60, row, col))
            board[row][col] = 0
        
        for row, col in valid_moves:
            neighbor_count = 0
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = row + dr, col + dc
                    if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board[nr][nc] != 0:
                        neighbor_count += 1
            if neighbor_count > 0:
                dist = abs(row - center) + abs(col - center)
                candidates.append((10 - dist // 3, row, col))
        
        if not candidates:
            for row, col in valid_moves:
                dist = abs(row - center) + abs(col - center)
                candidates.append((-dist, row, col))
        
        candidates.sort(reverse=True)
        
        top_n = min(5, len(candidates))
        top_candidates = candidates[:top_n]
        
        if random.random() < self.random_chance:
            return random.choice([(r, c) for _, r, c in top_candidates])
        
        return top_candidates[0][1], top_candidates[0][2]


class StrongAI:
    def __init__(self):
        self.DEPTH = 5
        self.mode = 'strong'
        self.experience = load_experience()
        self.current_game_history = []
        self.init_formation_patterns()
    
    def init_formation_patterns(self):
        self.formations = {
            'pu_yue': [
                [(7, 7), (7, 8), (8, 6), (8, 9), (6, 6), (6, 9), (9, 6), (9, 9)],
                [(7, 7), (7, 8), (8, 6), (8, 9), (6, 7), (9, 7)],
            ],
            'hua_yue': [
                [(7, 7), (7, 8), (8, 7), (6, 6), (6, 8), (9, 6), (9, 8)],
                [(7, 7), (7, 8), (8, 7), (8, 8), (6, 6), (6, 9), (9, 6), (9, 9)],
            ],
            'cang_long': [
                [(7, 7), (7, 8), (7, 9), (6, 6), (8, 6), (6, 10), (8, 10)],
                [(7, 7), (7, 8), (7, 9), (8, 8), (8, 9), (6, 8), (6, 9)],
            ],
            'double_three': [
                [(7, 7), (7, 8), (8, 7)],
                [(7, 7), (8, 8), (6, 8)],
                [(7, 7), (7, 8), (6, 8)],
                [(7, 7), (8, 7), (8, 8)],
            ],
            'open_four': [
                [(7, 7), (7, 8), (7, 9), (7, 10)],
                [(7, 7), (8, 7), (9, 7), (10, 7)],
                [(7, 7), (8, 8), (9, 9), (10, 10)],
                [(7, 7), (8, 6), (9, 5), (10, 4)],
            ],
            'fork_three': [
                [(7, 7), (7, 8), (8, 7), (9, 7)],
                [(7, 7), (8, 7), (7, 8), (7, 9)],
                [(7, 7), (8, 8), (7, 8), (6, 8)],
                [(7, 7), (8, 8), (8, 7), (8, 9)],
            ],
            'shield': [
                [(7, 7), (7, 8), (8, 6), (8, 8), (9, 7)],
                [(7, 7), (8, 7), (6, 8), (8, 8), (7, 9)],
            ],
            'wing': [
                [(7, 7), (7, 8), (6, 6), (6, 8), (8, 6), (8, 8)],
                [(7, 7), (8, 7), (6, 6), (8, 6), (6, 8), (8, 8)],
            ],
        }
        
        self.formation_scores = {
            'pu_yue': 200000,
            'hua_yue': 200000,
            'cang_long': 180000,
            'double_three': 150000,
            'open_four': 100000,
            'fork_three': 80000,
            'shield': 50000,
            'wing': 50000,
        }
        
        self.formation_responses = {
            'pu_yue': [(6, 7), (8, 7), (7, 6), (7, 9)],
            'hua_yue': [(6, 7), (8, 7), (7, 6), (7, 9)],
            'cang_long': [(6, 7), (8, 7)],
            'double_three': [(6, 9), (8, 9), (6, 6), (8, 6)],
            'open_four': [(6, 7), (11, 7), (7, 6), (7, 11)],
            'fork_three': [(6, 9), (9, 8), (9, 6), (6, 8)],
            'shield': [(6, 6), (6, 9), (9, 6), (9, 9)],
            'wing': [(6, 7), (8, 7), (7, 6), (7, 9)],
        }
    
    def set_mode(self, mode):
        self.mode = mode
    
    def reset_game(self):
        self.current_game_history = []
    
    def detect_formation(self, board, player):
        detected = []
        
        for name, patterns in self.formations.items():
            for pattern in patterns:
                match_count = 0
                for (r, c) in pattern:
                    if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == player:
                        match_count += 1
                
                if match_count >= len(pattern) - 1:
                    empty_pos = []
                    for (r, c) in pattern:
                        if 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == 0:
                            empty_pos.append((r, c))
                    
                    if empty_pos:
                        detected.append({
                            'name': name,
                            'score': self.formation_scores[name],
                            'empty_pos': empty_pos,
                        })
        
        return detected
    
    def evaluate_formation_score(self, board, player):
        formations = self.detect_formation(board, player)
        total_score = 0
        
        for f in formations:
            total_score += f['score']
        
        return total_score
    
    def get_move(self, board):
        board_copy = [row[:] for row in board]
        fingerprint = get_board_fingerprint(board_copy)
        
        if fingerprint in self.experience['learned_patterns']:
            learned_move = self.experience['learned_patterns'][fingerprint]
            if board_copy[learned_move[0]][learned_move[1]] == 0:
                self.current_game_history.append((fingerprint, learned_move))
                return learned_move
        
        ai_formations = self.detect_formation(board_copy, 2)
        player_formations = self.detect_formation(board_copy, 1)
        
        for f in ai_formations:
            for (r, c) in f['empty_pos']:
                board_copy[r][c] = 2
                if self._check_win(board_copy, r, c, 2):
                    board_copy[r][c] = 0
                    self.current_game_history.append((fingerprint, (r, c)))
                    return (r, c)
                board_copy[r][c] = 0
        
        for f in player_formations:
            for (r, c) in f['empty_pos']:
                board_copy[r][c] = 1
                if self._check_win(board_copy, r, c, 1):
                    board_copy[r][c] = 0
                    self.current_game_history.append((fingerprint, (r, c)))
                    return (r, c)
                board_copy[r][c] = 0
        
        for f in ai_formations:
            if f['score'] >= 80000:
                for (r, c) in f['empty_pos']:
                    if board_copy[r][c] == 0:
                        self.current_game_history.append((fingerprint, (r, c)))
                        return (r, c)
        
        for f in player_formations:
            if f['score'] >= 80000:
                for (r, c) in f['empty_pos']:
                    if board_copy[r][c] == 0:
                        self.current_game_history.append((fingerprint, (r, c)))
                        return (r, c)
        
        if HAS_NUMBA:
            board_np = np.array(board, dtype=np.int32)
            if self.mode == 'medium':
                row, col = get_best_move_medium(board_np)
            else:
                row, col = get_best_move(board_np)
            if row >= 0 and col >= 0:
                self.current_game_history.append((fingerprint, (row, col)))
                return (row, col)
        
        move = self.fallback_get_move(board)
        if move:
            self.current_game_history.append((fingerprint, move))
        return move
    
    def learn_from_defeat(self, board, winner):
        if winner == 1:
            for fingerprint, move in self.current_game_history:
                key = str(fingerprint)
                if key not in self.experience['bad_moves']:
                    self.experience['bad_moves'].append(key)
                if key in self.experience['learned_patterns']:
                    del self.experience['learned_patterns'][key]
            
            self.analyze_defeat(board)
            
            save_experience(self.experience)
            self.DEPTH = min(7, self.DEPTH + 1)
    
    def analyze_defeat(self, board):
        board_copy = [row[:] for row in board]
        moves = []
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if board_copy[r][c] == 1:
                    moves.append((r, c))
        
        if len(moves) >= 5:
            last_five = moves[-5:]
            for i in range(len(last_five)):
                test_board = [row[:] for row in board_copy]
                for j in range(i + 1, len(last_five)):
                    test_board[last_five[j][0]][last_five[j][1]] = 0
                
                fp = get_board_fingerprint(test_board)
                key = str(fp)
                
                for r in range(BOARD_SIZE):
                    for c in range(BOARD_SIZE):
                        if test_board[r][c] == 0:
                            test_board[r][c] = 2
                            if self._check_win(test_board, r, c, 2):
                                if key not in self.experience['learned_patterns']:
                                    self.experience['learned_patterns'][str(fp)] = (r, c)
                            elif self._would_block_win(test_board, r, c):
                                if key not in self.experience['learned_patterns']:
                                    self.experience['learned_patterns'][str(fp)] = (r, c)
                            test_board[r][c] = 0
    
    def _check_win(self, board, row, col, player):
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        for dx, dy in directions:
            count = 1
            r, c = row + dx, col + dy
            while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == player:
                count += 1
                r += dx
                c += dy
            r, c = row - dx, col - dy
            while 0 <= r < BOARD_SIZE and 0 <= c < BOARD_SIZE and board[r][c] == player:
                count += 1
                r -= dx
                c -= dy
            if count >= 5:
                return True
        return False
    
    def _would_block_win(self, board, row, col):
        test_board = [r[:] for r in board]
        test_board[row][col] = 1
        return self._check_win(test_board, row, col, 1)
    
    def fallback_get_move(self, board):
        directions = [(0, 1), (1, 0), (1, 1), (1, -1)]
        SCORES = {
            'five': 1000000,
            'open_four': 50000,
            'four': 10000,
            'open_three': 5000,
            'three': 500,
            'open_two': 100,
            'two': 10,
        }
        
        def check_pattern(r, c, player, dx, dy):
            left_open = False
            right_open = False
            count = 1
            
            nr, nc = r + dx, c + dy
            while 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board[nr][nc] == player:
                count += 1
                nr += dx
                nc += dy
            if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board[nr][nc] == 0:
                right_open = True
            
            nr, nc = r - dx, c - dy
            while 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board[nr][nc] == player:
                count += 1
                nr -= dx
                nc -= dy
            if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board[nr][nc] == 0:
                left_open = True
            
            both_open = left_open and right_open
            
            if count >= 5:
                return 'five'
            elif count == 4:
                return 'open_four' if both_open else 'four'
            elif count == 3:
                return 'open_three' if both_open else 'three'
            elif count == 2:
                return 'open_two' if both_open else 'two'
            return None
        
        candidates = []
        center = BOARD_SIZE // 2
        
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                if board[row][col] == 0:
                    neighbor_count = 0
                    for dr in [-1, 0, 1]:
                        for dc in [-1, 0, 1]:
                            if dr == 0 and dc == 0:
                                continue
                            nr, nc = row + dr, col + dc
                            if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and board[nr][nc] != 0:
                                neighbor_count += 1
                    
                    if neighbor_count > 0:
                        dist = abs(row - center) + abs(col - center)
                        candidates.append((-neighbor_count, dist, row, col))
        
        if not candidates:
            return (center, center)
        
        candidates.sort()
        candidates = [(r, c) for _, _, r, c in candidates[:20]]
        
        for row, col in candidates:
            board[row][col] = 2
            has_win = False
            for dx, dy in directions:
                if check_pattern(row, col, 2, dx, dy) == 'five':
                    has_win = True
                    break
            board[row][col] = 0
            if has_win:
                return (row, col)
        
        for row, col in candidates:
            board[row][col] = 1
            has_win = False
            for dx, dy in directions:
                if check_pattern(row, col, 1, dx, dy) == 'five':
                    has_win = True
                    break
            board[row][col] = 0
            if has_win:
                return (row, col)
        
        for row, col in candidates:
            board[row][col] = 2
            has_open_four = False
            for dx, dy in directions:
                if check_pattern(row, col, 2, dx, dy) == 'open_four':
                    has_open_four = True
                    break
            board[row][col] = 0
            if has_open_four:
                return (row, col)
        
        for row, col in candidates:
            board[row][col] = 1
            has_open_four = False
            for dx, dy in directions:
                if check_pattern(row, col, 1, dx, dy) == 'open_four':
                    has_open_four = True
                    break
            board[row][col] = 0
            if has_open_four:
                return (row, col)
        
        for row, col in candidates:
            board[row][col] = 2
            has_four = False
            for dx, dy in directions:
                if check_pattern(row, col, 2, dx, dy) == 'four':
                    has_four = True
                    break
            board[row][col] = 0
            if has_four:
                return (row, col)
        
        for row, col in candidates:
            board[row][col] = 1
            has_four = False
            for dx, dy in directions:
                if check_pattern(row, col, 1, dx, dy) == 'four':
                    has_four = True
                    break
            board[row][col] = 0
            if has_four:
                return (row, col)
        
        best_move = None
        best_score = float('-inf')
        
        for row, col in candidates:
            board[row][col] = 2
            score = 0
            
            for dx, dy in directions:
                pattern = check_pattern(row, col, 2, dx, dy)
                if pattern:
                    score += SCORES.get(pattern, 0)
                
                opp_pattern = check_pattern(row, col, 1, dx, dy)
                if opp_pattern:
                    score -= SCORES.get(opp_pattern, 0) * 0.9
            
            dist = abs(row - center) + abs(col - center)
            score += (BOARD_SIZE - dist) * 2
            
            board[row][col] = 0
            
            if score > best_score:
                best_score = score
                best_move = (row, col)
        
        return best_move


class GameUI:
    def __init__(self):
        self.board = GameBoard()
        self.weak_ai = WeakAI()
        self.strong_ai = StrongAI()
        self.game_mode = 'ai'
        self.ai_mode = 'strong'
        self.ai_modes = ['weak', 'medium', 'strong']
        self.ai_mode_names = ['弱AI', '中AI', '强AI']
        self.ai = self.strong_ai
        
        font_path = os.path.join(os.path.dirname(__file__), 'font.ttf')
        try:
            self.font = pygame.font.Font(font_path, 36)
            self.small_font = pygame.font.Font(font_path, 24)
        except:
            self.font = pygame.font.Font(None, 36)
            self.small_font = pygame.font.Font(None, 24)
        
        self.hover_pos = None
        self.animation_pos = None
        self.animation_player = None
        self.animation_progress = 0
        self.restart_btn = None
        self.undo_btn = None
        self.mode_btn = None
        self.ai_mode_btn = None
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.thinking = False

    def update_scale(self, width, height):
        target_cell = min(width, height) / (BOARD_SIZE + 1)
        self.scale = target_cell / CELL_SIZE
        
        board_pixel_size = (BOARD_SIZE - 1) * CELL_SIZE * self.scale
        self.offset_x = (width - board_pixel_size) / 2
        self.offset_y = (height - board_pixel_size) / 2

    def get_board_pos(self, mouse_x, mouse_y):
        col = int((mouse_x - self.offset_x + CELL_SIZE * self.scale / 2) / (CELL_SIZE * self.scale))
        row = int((mouse_y - self.offset_y + CELL_SIZE * self.scale / 2) / (CELL_SIZE * self.scale))
        
        if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
            return row, col
        return None

    def draw_board(self):
        width, height = screen.get_size()
        self.update_scale(width, height)
        
        screen.fill(BOARD_COLOR)
        
        for i in range(BOARD_SIZE):
            x1 = self.offset_x
            y1 = self.offset_y + i * CELL_SIZE * self.scale
            x2 = self.offset_x + (BOARD_SIZE - 1) * CELL_SIZE * self.scale
            y2 = y1
            pygame.draw.line(screen, BLACK, (x1, y1), (x2, y2), max(1, int(1 * self.scale)))
            
            x1 = self.offset_x + i * CELL_SIZE * self.scale
            y1 = self.offset_y
            x2 = x1
            y2 = self.offset_y + (BOARD_SIZE - 1) * CELL_SIZE * self.scale
            pygame.draw.line(screen, BLACK, (x1, y1), (x2, y2), max(1, int(1 * self.scale)))
        
        star_points = [(3, 3), (3, 11), (7, 7), (11, 3), (11, 11)]
        for row, col in star_points:
            x = self.offset_x + col * CELL_SIZE * self.scale
            y = self.offset_y + row * CELL_SIZE * self.scale
            pygame.draw.circle(screen, BLACK, (x, y), max(2, int(4 * self.scale)))
        
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                if self.board.board[row][col] != 0:
                    self.draw_piece(row, col, self.board.board[row][col])
        
        if self.board.win_line:
            self.draw_win_line()
        
        if self.hover_pos and not self.board.game_over:
            self.draw_hover_preview()
        
        if self.animation_pos:
            self.draw_animation()

    def draw_piece(self, row, col, player):
        x = self.offset_x + col * CELL_SIZE * self.scale
        y = self.offset_y + row * CELL_SIZE * self.scale
        radius = int(18 * self.scale)
        
        if player == 1:
            pygame.draw.circle(screen, BLACK, (x, y), radius)
            pygame.draw.circle(screen, (30, 30, 30), (x - int(2 * self.scale), y - int(2 * self.scale)), int(16 * self.scale))
        else:
            pygame.draw.circle(screen, WHITE, (x, y), radius)
            pygame.draw.circle(screen, (220, 220, 220), (x - int(2 * self.scale), y - int(2 * self.scale)), int(16 * self.scale))
            pygame.draw.circle(screen, BLACK, (x, y), radius, 1)

    def draw_hover_preview(self):
        row, col = self.hover_pos
        x = self.offset_x + col * CELL_SIZE * self.scale
        y = self.offset_y + row * CELL_SIZE * self.scale
        radius = int(18 * self.scale)
        
        if self.board.current_player == 1:
            pygame.draw.circle(screen, BLACK, (x, y), radius, 2)
        else:
            pygame.draw.circle(screen, WHITE, (x, y), radius, 2)
            pygame.draw.circle(screen, BLACK, (x, y), radius, 1)

    def draw_animation(self):
        row, col = self.animation_pos
        x = self.offset_x + col * CELL_SIZE * self.scale
        y = self.offset_y + row * CELL_SIZE * self.scale
        radius = int(18 * self.scale * self.animation_progress)
        
        if self.animation_player == 2:
            pygame.draw.circle(screen, WHITE, (x, y), radius)
            pygame.draw.circle(screen, BLACK, (x, y), radius, 1)
        else:
            pygame.draw.circle(screen, BLACK, (x, y), radius)
        
        self.animation_progress += 0.15
        if self.animation_progress >= 1:
            self.animation_pos = None
            self.animation_player = None
            self.animation_progress = 0

    def draw_win_line(self):
        if not self.board.win_line:
            return
        
        start = self.board.win_line[0]
        end = self.board.win_line[-1]
        
        x1 = self.offset_x + start[1] * CELL_SIZE * self.scale
        y1 = self.offset_y + start[0] * CELL_SIZE * self.scale
        x2 = self.offset_x + end[1] * CELL_SIZE * self.scale
        y2 = self.offset_y + end[0] * CELL_SIZE * self.scale
        
        pygame.draw.line(screen, RED, (x1, y1), (x2, y2), max(2, int(4 * self.scale)))

    def draw_ui(self):
        width, height = screen.get_size()
        
        if self.board.game_over:
            winner_text = "黑方获胜！" if self.board.winner == 1 else "白方获胜！"
            text = self.font.render(winner_text, True, RED)
            text_rect = text.get_rect(center=(width // 2, 25))
            screen.blit(text, text_rect)
        elif self.thinking:
            text = self.font.render("AI思考中...", True, BLUE)
            text_rect = text.get_rect(center=(width // 2, 25))
            screen.blit(text, text_rect)
        else:
            player_text = "轮到黑方" if self.board.current_player == 1 else "轮到白方"
            text = self.font.render(player_text, True, BLACK)
            text_rect = text.get_rect(center=(width // 2, 25))
            screen.blit(text, text_rect)
        
        btn_width = 100
        btn_height = 40
        btn_margin = 15
        
        self.restart_btn = pygame.Rect(width - btn_width - btn_margin, height - btn_height - btn_margin, btn_width, btn_height)
        self.undo_btn = pygame.Rect(width - btn_width * 2 - btn_margin * 2, height - btn_height - btn_margin, btn_width, btn_height)
        
        if self.game_mode == 'ai':
            self.ai_mode_btn = pygame.Rect(width - btn_width * 3 - btn_margin * 3, height - btn_height - btn_margin, btn_width, btn_height)
            self.mode_btn = pygame.Rect(width - btn_width * 4 - btn_margin * 4, height - btn_height - btn_margin, btn_width, btn_height)
        else:
            self.mode_btn = pygame.Rect(width - btn_width * 3 - btn_margin * 3, height - btn_height - btn_margin, btn_width, btn_height)
        
        pygame.draw.rect(screen, GRAY, self.restart_btn, 2)
        pygame.draw.rect(screen, GRAY, self.undo_btn, 2)
        pygame.draw.rect(screen, GREEN, self.mode_btn, 2)
        
        restart_text = self.small_font.render("重新开始", True, BLACK)
        undo_text = self.small_font.render("悔棋", True, BLACK)
        mode_text = self.small_font.render("双人模式" if self.game_mode == 'ai' else "AI模式", True, BLACK)
        
        screen.blit(restart_text, restart_text.get_rect(center=self.restart_btn.center))
        screen.blit(undo_text, undo_text.get_rect(center=self.undo_btn.center))
        screen.blit(mode_text, mode_text.get_rect(center=self.mode_btn.center))
        
        if self.game_mode == 'ai':
            ai_btn_color = BLUE if self.ai_mode != 'weak' else GRAY
            pygame.draw.rect(screen, ai_btn_color, self.ai_mode_btn, 2)
            
            current_mode_idx = 0
            for i, mode in enumerate(self.ai_modes):
                if mode == self.ai_mode:
                    current_mode_idx = i
                    break
            ai_mode_text = self.small_font.render(self.ai_mode_names[current_mode_idx], True, BLACK)
            screen.blit(ai_mode_text, ai_mode_text.get_rect(center=self.ai_mode_btn.center))

    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            pos = self.get_board_pos(event.pos[0], event.pos[1])
            if pos and self.board.board[pos[0]][pos[1]] == 0:
                self.hover_pos = pos
            else:
                self.hover_pos = None
        
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.restart_btn and self.restart_btn.collidepoint(event.pos):
                if self.board.game_over and self.board.winner == 1 and self.game_mode == 'ai':
                    if hasattr(self.ai, 'learn_from_defeat'):
                        self.ai.learn_from_defeat(self.board.board, 1)
                if hasattr(self.ai, 'reset_game'):
                    self.ai.reset_game()
                self.board.reset()
                return
            
            if self.undo_btn and self.undo_btn.collidepoint(event.pos):
                undo_steps = 2 if (self.board.current_player == 1 and self.game_mode == 'ai') else 1
                self.board.undo(undo_steps)
                return
            
            if self.mode_btn and self.mode_btn.collidepoint(event.pos):
                self.game_mode = 'vs' if self.game_mode == 'ai' else 'ai'
                if self.game_mode == 'ai':
                    if self.ai_mode == 'strong':
                        self.ai = self.strong_ai
                        self.strong_ai.set_mode('strong')
                    elif self.ai_mode == 'medium':
                        self.ai = self.strong_ai
                        self.strong_ai.set_mode('medium')
                    else:
                        self.ai = self.weak_ai
                self.board.reset()
                return
            
            if self.game_mode == 'ai' and self.ai_mode_btn and self.ai_mode_btn.collidepoint(event.pos):
                current_idx = 0
                for i, mode in enumerate(self.ai_modes):
                    if mode == self.ai_mode:
                        current_idx = i
                        break
                next_idx = (current_idx + 1) % len(self.ai_modes)
                self.ai_mode = self.ai_modes[next_idx]
                
                if self.ai_mode == 'strong':
                    self.ai = self.strong_ai
                    self.strong_ai.set_mode('strong')
                elif self.ai_mode == 'medium':
                    self.ai = self.strong_ai
                    self.strong_ai.set_mode('medium')
                else:
                    self.ai = self.weak_ai
                
                self.board.reset()
                return
            
            pos = self.get_board_pos(event.pos[0], event.pos[1])
            if pos and self.board.make_move(pos[0], pos[1]):
                self.animation_pos = pos
                self.animation_player = self.board.history[-1][2]
                
                if self.game_mode == 'ai' and not self.board.game_over and self.board.current_player == 2:
                    self.thinking = True
                    if self.ai_mode == 'weak':
                        delay = 100
                    elif self.ai_mode == 'medium':
                        delay = 300
                    else:
                        delay = 500
                    pygame.time.set_timer(pygame.USEREVENT, delay)

    def run(self):
        clock = pygame.time.Clock()
        
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                
                elif event.type == pygame.VIDEORESIZE:
                    screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                
                elif event.type == pygame.USEREVENT:
                    pygame.time.set_timer(pygame.USEREVENT, 0)
                    if self.game_mode == 'ai' and not self.board.game_over and self.board.current_player == 2:
                        ai_move = self.ai.get_move(self.board.board)
                        if ai_move:
                            self.board.make_move(ai_move[0], ai_move[1])
                            self.animation_pos = ai_move
                            self.animation_player = 2
                        self.thinking = False
                
                else:
                    self.handle_event(event)
            
            self.draw_board()
            self.draw_ui()
            
            pygame.display.flip()
            clock.tick(30)


if __name__ == "__main__":
    game = GameUI()
    game.run()