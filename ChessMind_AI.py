import tkinter as tk
from tkinter import ttk, messagebox
import chess
import math
import time
import threading

BG = "#101820"
PANEL = "#18232F"
PANEL2 = "#202E3B"
TEXT = "#F2F5F7"
MUTED = "#AAB7C4"
ACCENT = "#5BD6A2"
BLUE = "#69A9FF"
GOLD = "#F5C96A"
RED = "#F07878"
LIGHT = "#E8EDF2"
DARK = "#71917D"
SELECT = "#F5D76E"
HIGHLIGHT = "#6ACB91"
FONT = "Segoe UI"

PIECES = {
    "K": "♔", "Q": "♕", "R": "♖", "B": "♗", "N": "♘", "P": "♙",
    "k": "♚", "q": "♛", "r": "♜", "b": "♝", "n": "♞", "p": "♟"
}

VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 335,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000
}

MODES = {
    "Easy": 1,
    "Medium": 2,
    "Hard": 3,
    "Expert": 4
}


class MinimaxEngine:
    def __init__(self):
        self.nodes = 0
        self.cutoffs = 0
        self.started = 0
        self.transposition = {}

    def evaluate(self, board):
        if board.is_checkmate():
            return -1000000 if board.turn == chess.WHITE else 1000000
        if board.is_game_over(claim_draw=True):
            return 0

        score = 0
        phase = 0

        for square, piece in board.piece_map().items():
            value = VALUES[piece.piece_type]
            file_idx = chess.square_file(square)
            rank_idx = chess.square_rank(square)
            relative_rank = rank_idx if piece.color == chess.WHITE else 7 - rank_idx
            center = 7 - (abs(3.5 - file_idx) + abs(3.5 - rank_idx))
            if piece.piece_type == chess.PAWN:
                value += relative_rank * 9
                if file_idx in (3, 4):
                    value += 8
            elif piece.piece_type == chess.KNIGHT:
                value += center * 9
            elif piece.piece_type == chess.BISHOP:
                value += center * 5
            elif piece.piece_type == chess.QUEEN:
                value += center * 2
            elif piece.piece_type == chess.ROOK:
                if relative_rank == 6:
                    value += 18
            elif piece.piece_type == chess.KING:
                if board.fullmove_number < 20:
                    value -= center * 5
                else:
                    value += center * 7
            score += value if piece.color == chess.WHITE else -value
            if piece.piece_type in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT):
                phase += 1

        score += 12 * (len(list(board.legal_moves)) if board.turn == chess.WHITE else -len(list(board.legal_moves)))
        if board.is_check():
            score += -35 if board.turn == chess.WHITE else 35
        return score

    def move_order(self, board, move):
        score = 0
        if board.is_capture(move):
            victim = board.piece_at(move.to_square)
            if victim is None and board.is_en_passant(move):
                victim_value = VALUES[chess.PAWN]
            else:
                victim_value = VALUES[victim.piece_type] if victim else 0
            attacker = board.piece_at(move.from_square)
            attacker_value = VALUES[attacker.piece_type] if attacker else 0
            score += 10 * victim_value - attacker_value
        if move.promotion:
            score += VALUES[move.promotion]
        if board.gives_check(move):
            score += 45
        return score

    def ordered_moves(self, board):
        return sorted(list(board.legal_moves), key=lambda m: self.move_order(board, m), reverse=True)

    def negamax(self, board, depth, alpha, beta, ply=0):
        self.nodes += 1

        if board.is_checkmate():
            return -1000000 + ply, []
        if board.is_game_over(claim_draw=True):
            return 0, []
        if depth == 0:
            value = self.evaluate(board)
            return (value if board.turn == chess.WHITE else -value), []

        key = (board.fen(), depth)
        if key in self.transposition:
            cached = self.transposition[key]
            if cached[1] is not None:
                return cached[0], [cached[1]]

        best_score = -math.inf
        best_line = []
        for move in self.ordered_moves(board):
            board.push(move)
            child_score, child_line = self.negamax(board, depth - 1, -beta, -alpha, ply + 1)
            score = -child_score
            board.pop()

            if score > best_score:
                best_score = score
                best_line = [move] + child_line

            alpha = max(alpha, score)
            if alpha >= beta:
                self.cutoffs += 1
                break

        self.transposition[key] = (best_score, best_line[0] if best_line else None)
        return best_score, best_line

    def analyze(self, board, depth):
        self.nodes = 0
        self.cutoffs = 0
        self.transposition = {}
        self.started = time.perf_counter()
        working = board.copy()
        score, line = self.negamax(working, depth, -math.inf, math.inf)
        elapsed = max(time.perf_counter() - self.started, 0.0001)
        white_score = score if board.turn == chess.WHITE else -score
        return {
            "move": line[0] if line else None,
            "line": line,
            "score": white_score,
            "nodes": self.nodes,
            "cutoffs": self.cutoffs,
            "seconds": elapsed,
            "nps": int(self.nodes / elapsed)
        }


class ChessMindApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ChessMind AI | Minimax Chess Studio")
        self.root.geometry("1180x790")
        self.root.minsize(1050, 720)
        self.root.configure(bg=BG)

        self.board = chess.Board()
        self.history = []
        self.selected = None
        self.hint_move = None
        self.best_move = None
        self.mode = tk.StringVar(value="Medium")
        self.tab = tk.StringVar(value="Play")
        self.engine = MinimaxEngine()
        self.analysis = None
        self.busy = False
        self.ai_enabled = tk.BooleanVar(value=True)
        self.status_text = tk.StringVar(value="White to move")
        self.eval_text = tk.StringVar(value="Evaluation: 0.00")
        self.depth_text = tk.StringVar(value="Search depth: —")
        self.node_text = tk.StringVar(value="Positions analyzed: —")
        self.time_text = tk.StringVar(value="Search time: —")
        self.best_text = tk.StringVar(value="Best move: —")
        self.hint_text = tk.StringVar(value="Select a piece to see legal moves.")
        self.last_move = None

        self._build_ui()
        self._draw_board()
        self._refresh_all()

    def _build_ui(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=22, pady=(16, 12))

        tk.Label(header, text="CHESSMIND", bg=BG, fg=ACCENT,
                 font=(FONT, 23, "bold")).pack(side="left")
        tk.Label(header, text="AI CHESS STUDIO  /  MINIMAX ANALYSIS",
                 bg=BG, fg=MUTED, font=(FONT, 9, "bold")).pack(side="left", padx=15, pady=(10, 0))
        tk.Label(header, text="PYTHON PROJECT", bg=PANEL2, fg=TEXT,
                 font=(FONT, 9, "bold"), padx=12, pady=7).pack(side="right")

        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=22, pady=(0, 18))

        self.board_card = tk.Frame(body, bg=PANEL, padx=14, pady=14)
        self.board_card.pack(side="left", fill="y")

        board_header = tk.Frame(self.board_card, bg=PANEL)
        board_header.pack(fill="x", pady=(0, 10))
        tk.Label(board_header, text="Live board", bg=PANEL, fg=TEXT,
                 font=(FONT, 14, "bold")).pack(side="left")
        tk.Label(board_header, text="8 × 8", bg=PANEL, fg=MUTED,
                 font=(FONT, 10)).pack(side="right")

        self.board_frame = tk.Frame(self.board_card, bg=PANEL)
        self.board_frame.pack()
        self.square_buttons = {}
        for row in range(8):
            rank_name = str(8 - row)
            tk.Label(self.board_frame, text=rank_name, bg=PANEL, fg=MUTED,
                     font=(FONT, 9, "bold"), width=2).grid(row=row, column=0, sticky="nsew")
            for col in range(8):
                square = chess.square(col, 7 - row)
                button = tk.Button(
                    self.board_frame, text="", width=2, height=1,
                    font=("DejaVu Sans", 31), relief="flat", bd=0,
                    highlightthickness=0, cursor="hand2",
                    command=lambda sq=square: self._on_square(sq)
                )
                button.grid(row=row, column=col + 1, sticky="nsew")
                self.square_buttons[square] = button
            self.board_frame.grid_rowconfigure(row, weight=1, minsize=65)
        self.board_frame.grid_columnconfigure(0, weight=0, minsize=22)
        for col in range(8):
            self.board_frame.grid_columnconfigure(col + 1, weight=1, minsize=65)

        files_row = tk.Frame(self.board_card, bg=PANEL)
        files_row.pack(fill="x", pady=(7, 0))
        tk.Label(files_row, text="", bg=PANEL, width=2).pack(side="left")
        for file_name in "abcdefgh":
            tk.Label(files_row, text=file_name, bg=PANEL, fg=MUTED,
                     font=(FONT, 9, "bold")).pack(side="left", expand=True)

        board_footer = tk.Frame(self.board_card, bg=PANEL)
        board_footer.pack(fill="x", pady=(12, 0))
        tk.Label(board_footer, textvariable=self.status_text, bg=PANEL, fg=GOLD,
                 font=(FONT, 11, "bold")).pack(side="left")
        self.spinner_label = tk.Label(board_footer, text="", bg=PANEL, fg=ACCENT,
                                      font=(FONT, 9))
        self.spinner_label.pack(side="right")

        self.side = tk.Frame(body, bg=BG)
        self.side.pack(side="left", fill="both", expand=True, padx=(18, 0))

        mode_card = tk.Frame(self.side, bg=PANEL, padx=16, pady=14)
        mode_card.pack(fill="x")
        tk.Label(mode_card, text="GAME CONTROL", bg=PANEL, fg=MUTED,
                 font=(FONT, 9, "bold")).pack(anchor="w")
        controls = tk.Frame(mode_card, bg=PANEL)
        controls.pack(fill="x", pady=(9, 0))
        tk.Label(controls, text="Difficulty", bg=PANEL, fg=TEXT,
                 font=(FONT, 10, "bold")).pack(side="left")
        mode_box = ttk.Combobox(controls, textvariable=self.mode, values=list(MODES),
                                state="readonly", width=12)
        mode_box.pack(side="left", padx=(9, 15))
        mode_box.bind("<<ComboboxSelected>>", self._mode_changed)
        tk.Checkbutton(controls, text="Play vs AI", variable=self.ai_enabled,
                       bg=PANEL, fg=TEXT, selectcolor=PANEL2, activebackground=PANEL,
                       activeforeground=TEXT, font=(FONT, 9),
                       command=self._refresh_all).pack(side="left")

        buttons = tk.Frame(mode_card, bg=PANEL)
        buttons.pack(fill="x", pady=(12, 0))
        self._button(buttons, "Best Move", self._analyze_best, ACCENT, BG).pack(side="left", fill="x", expand=True)
        self._button(buttons, "Hint", self._show_hint, BLUE, BG).pack(side="left", fill="x", expand=True, padx=7)
        self._button(buttons, "Undo", self._undo, PANEL2, TEXT).pack(side="left", fill="x", expand=True)
        self._button(buttons, "New Game", self._restart, PANEL2, TEXT).pack(side="left", fill="x", expand=True, padx=(7, 0))

        tabs = tk.Frame(self.side, bg=BG)
        tabs.pack(fill="x", pady=(13, 0))
        self.tab_buttons = {}
        for label in ("Play", "Analysis", "Move History"):
            btn = tk.Button(tabs, text=label, command=lambda t=label: self._set_tab(t),
                            relief="flat", bd=0, padx=12, pady=10,
                            font=(FONT, 10, "bold"), cursor="hand2")
            btn.pack(side="left", padx=(0, 5))
            self.tab_buttons[label] = btn

        self.content = tk.Frame(self.side, bg=PANEL, padx=16, pady=14)
        self.content.pack(fill="both", expand=True, pady=(2, 0))
        self._render_tab()

    def _button(self, parent, text, command, bg, fg):
        return tk.Button(parent, text=text, command=command, bg=bg, fg=fg,
                         activebackground=bg, activeforeground=fg, relief="flat",
                         bd=0, padx=10, pady=10, font=(FONT, 9, "bold"),
                         cursor="hand2")

    def _set_tab(self, tab):
        self.tab.set(tab)
        self._render_tab()

    def _mode_changed(self, event=None):
        self.hint_move = None
        self.best_move = None
        self._refresh_all()

    def _render_tab(self):
        for child in self.content.winfo_children():
            child.destroy()

        for label, button in self.tab_buttons.items():
            active = self.tab.get() == label
            button.configure(bg=ACCENT if active else PANEL, fg=BG if active else MUTED)

        if self.tab.get() == "Play":
            self._render_play_tab()
        elif self.tab.get() == "Analysis":
            self._render_analysis_tab()
        else:
            self._render_history_tab()

    def _section_title(self, parent, text, subtitle=None):
        tk.Label(parent, text=text, bg=PANEL, fg=TEXT,
                 font=(FONT, 14, "bold")).pack(anchor="w")
        if subtitle:
            tk.Label(parent, text=subtitle, bg=PANEL, fg=MUTED,
                     font=(FONT, 9), wraplength=420, justify="left").pack(anchor="w", pady=(4, 0))

    def _metric(self, parent, value, label):
        box = tk.Frame(parent, bg=PANEL2, padx=10, pady=10)
        tk.Label(box, text=value, bg=PANEL2, fg=ACCENT,
                 font=(FONT, 17, "bold")).pack(anchor="w")
        tk.Label(box, text=label, bg=PANEL2, fg=MUTED,
                 font=(FONT, 8, "bold")).pack(anchor="w", pady=(3, 0))
        return box

    def _render_play_tab(self):
        self._section_title(self.content, "Game overview", "Play against the AI or switch off Play vs AI for a two-player game.")
        status_card = tk.Frame(self.content, bg=PANEL2, padx=13, pady=12)
        status_card.pack(fill="x", pady=(13, 12))
        tk.Label(status_card, text="CURRENT POSITION", bg=PANEL2, fg=MUTED,
                 font=(FONT, 8, "bold")).pack(anchor="w")
        tk.Label(status_card, textvariable=self.status_text, bg=PANEL2, fg=GOLD,
                 font=(FONT, 13, "bold")).pack(anchor="w", pady=(5, 0))
        tk.Label(status_card, textvariable=self.hint_text, bg=PANEL2, fg=TEXT,
                 font=(FONT, 10), wraplength=410, justify="left").pack(anchor="w", pady=(6, 0))

        row = tk.Frame(self.content, bg=PANEL)
        row.pack(fill="x")
        self._metric(row, str(self.board.fullmove_number), "MOVE NUMBER").pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._metric(row, "White" if self.board.turn else "Black", "TO MOVE").pack(side="left", fill="x", expand=True, padx=6)
        self._metric(row, self.mode.get(), "AI LEVEL").pack(side="left", fill="x", expand=True, padx=(6, 0))

        tk.Label(self.content, text="QUICK GUIDE", bg=PANEL, fg=MUTED,
                 font=(FONT, 9, "bold")).pack(anchor="w", pady=(18, 7))
        for text in (
            "1. Files are the letters a–h along the bottom; ranks are numbers 1–8 on the left.",
            "2. A square name combines its letter and number, e.g. e2 or f3.",
            "3. Click one of your pieces, then a highlighted destination.",
            "4. Hint shows a move like e2 → e4: start square to destination square.",
            "5. Use Best Move or open Analysis to inspect the AI's suggestion."
        ):
            tk.Label(self.content, text=text, bg=PANEL, fg=TEXT, font=(FONT, 9),
                     anchor="w", justify="left").pack(fill="x", pady=3)

    def _render_analysis_tab(self):
        self._section_title(self.content, "Minimax analysis", "Alpha-Beta Pruning searches candidate moves and evaluates the resulting positions.")
        metrics = tk.Frame(self.content, bg=PANEL)
        metrics.pack(fill="x", pady=(13, 10))
        result = self.analysis
        values = [
            (f"{result['score'] / 100:+.2f}" if result else "—", "EVALUATION"),
            (f"{result['nodes']:,}" if result else "—", "NODES VISITED"),
            (f"{result['cutoffs']:,}" if result else "—", "ALPHA-BETA CUTS"),
        ]
        for i, (value, label) in enumerate(values):
            self._metric(metrics, value, label).grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 5, 0))
            metrics.grid_columnconfigure(i, weight=1, uniform="m")

        stats = tk.Frame(self.content, bg=PANEL2, padx=12, pady=12)
        stats.pack(fill="x")
        detail_rows = (
            ("Search depth", self.depth_text.get()),
            ("Search time", self.time_text.get()),
            ("Nodes per second", f"{result['nps']:,}" if result else "—"),
            ("Best move", self.best_text.get())
        )
        for row_index, (label, value) in enumerate(detail_rows):
            tk.Label(stats, text=label, bg=PANEL2, fg=MUTED,
                     font=(FONT, 9)).grid(row=row_index, column=0, sticky="w", pady=3)
            tk.Label(stats, text=value, bg=PANEL2, fg=TEXT,
                     font=(FONT, 10, "bold")).grid(row=row_index, column=1, sticky="e", padx=(15, 0), pady=3)
        stats.grid_columnconfigure(1, weight=1)

        tk.Label(self.content, text="PRINCIPAL VARIATION", bg=PANEL, fg=MUTED,
                 font=(FONT, 9, "bold")).pack(anchor="w", pady=(15, 6))
        pv = result["line"] if result else []
        if pv:
            temp = self.board.copy()
            parts = []
            for move in pv[:12]:
                if temp.turn == chess.WHITE:
                    parts.append(f"{temp.fullmove_number}.")
                elif not parts:
                    parts.append(f"{temp.fullmove_number}...")
                parts.append(temp.san(move))
                temp.push(move)
            pv_text = " ".join(parts)
        else:
            pv_text = "Click Best Move to run an analysis of the current position."
        tk.Label(self.content, text=pv_text, bg=PANEL2, fg=ACCENT,
                 font=(FONT, 11, "bold"), wraplength=430, justify="left",
                 padx=12, pady=12).pack(fill="x")

        tk.Label(self.content, text="EVALUATION GUIDE", bg=PANEL, fg=MUTED,
                 font=(FONT, 9, "bold")).pack(anchor="w", pady=(14, 6))
        tk.Label(self.content, text="+ values favor White · − values favor Black\nMaterial values: pawn 1.00 · knight 3.20 · bishop 3.35 · rook 5.00 · queen 9.00",
                 bg=PANEL, fg=TEXT, font=(FONT, 9), justify="left",
                 wraplength=430).pack(anchor="w")

        action_row = tk.Frame(self.content, bg=PANEL)
        action_row.pack(fill="x", pady=(15, 0))
        self._button(action_row, "Analyze Position", self._analyze_best, ACCENT, BG).pack(side="left")
        self._button(action_row, "Show Hint", self._show_hint, BLUE, BG).pack(side="left", padx=8)

    def _render_history_tab(self):
        self._section_title(self.content, "Move history", "Review played moves in standard algebraic notation.")
        container = tk.Frame(self.content, bg=PANEL)
        container.pack(fill="both", expand=True, pady=(12, 0))
        columns = ("number", "white", "black")
        tree = ttk.Treeview(container, columns=columns, show="headings", height=14)
        tree.heading("number", text="#")
        tree.heading("white", text="White")
        tree.heading("black", text="Black")
        tree.column("number", width=45, anchor="center")
        tree.column("white", width=120, anchor="center")
        tree.column("black", width=120, anchor="center")
        scroll = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        sans = []
        temp = chess.Board()
        for move in self.board.move_stack:
            sans.append((temp.fullmove_number, temp.san(move), temp.turn))
            temp.push(move)
        for index in range(0, len(sans), 2):
            num, white_san, _ = sans[index]
            black_san = sans[index + 1][1] if index + 1 < len(sans) else ""
            tree.insert("", "end", values=(num, white_san, black_san))

        if not sans:
            tk.Label(container, text="No moves played yet.", bg=PANEL, fg=MUTED,
                     font=(FONT, 10)).pack(pady=12)

    def _draw_board(self):
        legal_targets = set()
        if self.selected is not None:
            legal_targets = {m.to_square for m in self.board.legal_moves if m.from_square == self.selected}

        for square, button in self.square_buttons.items():
            piece = self.board.piece_at(square)
            file_idx = chess.square_file(square)
            rank_idx = chess.square_rank(square)
            base = LIGHT if (file_idx + rank_idx) % 2 == 1 else DARK
            if piece:
                if piece.color == chess.WHITE:
                    fg = "#17212B" if base == LIGHT else "#FFFDF5"
                else:
                    fg = "#111820" if base == LIGHT else "#F8FAFC"
            else:
                fg = TEXT

            if square == self.selected:
                base = SELECT
            elif square in legal_targets:
                base = HIGHLIGHT
            elif self.hint_move and square in (self.hint_move.from_square, self.hint_move.to_square):
                base = GOLD
            elif self.best_move and square in (self.best_move.from_square, self.best_move.to_square):
                base = BLUE
            elif self.last_move and square in (self.last_move.from_square, self.last_move.to_square):
                base = "#A8C7FA"

            symbol = PIECES[piece.symbol()] if piece else ""
            button.configure(text=symbol, bg=base, fg=fg,
                             activebackground=base, activeforeground=fg)
            button.configure(font=("DejaVu Sans", 31 if piece else 20))

    def _on_square(self, square):
        if self.busy or self._game_over():
            return
        if self.ai_enabled.get() and self.board.turn == chess.BLACK:
            return

        piece = self.board.piece_at(square)
        if self.selected is None:
            if piece and piece.color == self.board.turn:
                self.selected = square
                self.hint_text.set("Choose a highlighted destination.")
            self._draw_board()
            return

        matching = [m for m in self.board.legal_moves if m.from_square == self.selected and m.to_square == square]
        if matching:
            move = matching[0]
            if any(m.promotion for m in matching):
                move = self._choose_promotion(matching)
                if move is None:
                    return
            self._play_move(move)
            return

        if piece and piece.color == self.board.turn:
            self.selected = square
            self.hint_text.set("Piece selected. Choose a highlighted destination.")
        else:
            self.selected = None
            self.hint_text.set("Selection cleared.")
        self._draw_board()

    def _choose_promotion(self, moves):
        choices = {m.promotion: m for m in moves}
        dialog = tk.Toplevel(self.root)
        dialog.title("Promote pawn")
        dialog.configure(bg=PANEL)
        dialog.transient(self.root)
        dialog.grab_set()
        tk.Label(dialog, text="Choose promotion piece", bg=PANEL, fg=TEXT,
                 font=(FONT, 11, "bold")).pack(padx=16, pady=(14, 8))
        result = {"move": choices.get(chess.QUEEN)}
        row = tk.Frame(dialog, bg=PANEL)
        row.pack(padx=12, pady=(0, 14))
        for piece_type, label in ((chess.QUEEN, "Queen"), (chess.ROOK, "Rook"),
                                  (chess.BISHOP, "Bishop"), (chess.KNIGHT, "Knight")):
            tk.Button(row, text=label, command=lambda p=piece_type: (result.update(move=choices[p]), dialog.destroy()),
                      bg=PANEL2, fg=TEXT, relief="flat", padx=8, pady=8).pack(side="left", padx=3)
        self.root.wait_window(dialog)
        return result["move"]

    def _play_move(self, move):
        san = self.board.san(move)
        self.board.push(move)
        self.last_move = move
        self.selected = None
        self.hint_move = None
        self.best_move = None
        self.analysis = None
        self.hint_text.set(f"Played {san}.")
        self._refresh_all()
        if self.ai_enabled.get() and not self._game_over() and self.board.turn == chess.BLACK:
            self.root.after(120, self._ai_move)

    def _ai_move(self):
        if self.busy or self._game_over() or self.board.turn != chess.BLACK or not self.ai_enabled.get():
            return
        self._start_analysis(MODES[self.mode.get()], play_result=True)

    def _start_analysis(self, depth, play_result=False):
        if self.busy or self._game_over():
            return
        self.busy = True
        self.spinner_label.configure(text="Engine thinking…")
        self.hint_text.set("Minimax is evaluating candidate moves.")
        self._refresh_all()

        board_copy = self.board.copy()
        engine = MinimaxEngine()

        def worker():
            result = engine.analyze(board_copy, depth)
            self.root.after(0, lambda: self._analysis_finished(result, play_result, board_copy.fen()))

        threading.Thread(target=worker, daemon=True).start()

    def _analysis_finished(self, result, play_result, original_fen):
        if self.board.fen() != original_fen:
            self.busy = False
            self.spinner_label.configure(text="")
            return
        self.busy = False
        self.spinner_label.configure(text="")
        self.analysis = result
        self.best_move = result["move"]
        self.hint_move = result["move"]
        self.depth_text.set(f"Search depth: {MODES[self.mode.get()]}")
        self.node_text.set(f"Positions analyzed: {result['nodes']:,}")
        self.time_text.set(f"Search time: {result['seconds']:.3f} s")
        if result["move"]:
            move = result["move"]
            san = self.board.san(move)
            coordinates = f"{chess.square_name(move.from_square)} → {chess.square_name(move.to_square)}"
            self.best_text.set(f"Best move: {san} ({coordinates})")
            self.hint_text.set(f"Suggested move: {coordinates} ({san}). Letters a–h, numbers 1–8.")
        else:
            self.best_text.set("Best move: —")
            self.hint_text.set("The game is over.")
        self.eval_text.set(f"Evaluation: {result['score'] / 100:+.2f}")
        if play_result and result["move"] and self.board.turn == chess.BLACK:
            move = result["move"]
            self.board.push(move)
            self.last_move = move
            self.selected = None
            self.hint_text.set(f"AI played {self.board.peek().uci()}.")
        self._refresh_all()

    def _analyze_best(self):
        self._set_tab("Analysis")
        self._start_analysis(MODES[self.mode.get()])

    def _show_hint(self):
        if self.busy or self._game_over():
            return
        self._start_analysis(MODES[self.mode.get()])

    def _undo(self):
        if self.busy or not self.board.move_stack:
            return
        self.board.pop()
        if self.ai_enabled.get() and self.board.move_stack and self.board.turn == chess.BLACK:
            self.board.pop()
        self.selected = None
        self.hint_move = None
        self.best_move = None
        self.analysis = None
        self.last_move = self.board.peek() if self.board.move_stack else None
        self.hint_text.set("Previous move restored.")
        self._refresh_all()

    def _restart(self):
        if self.busy:
            return
        self.board.reset()
        self.selected = None
        self.hint_move = None
        self.best_move = None
        self.analysis = None
        self.last_move = None
        self.depth_text.set("Search depth: —")
        self.node_text.set("Positions analyzed: —")
        self.time_text.set("Search time: —")
        self.best_text.set("Best move: —")
        self.hint_text.set("New game started.")
        self._refresh_all()

    def _game_over(self):
        if self.board.is_checkmate():
            winner = "Black" if self.board.turn == chess.WHITE else "White"
            self.status_text.set(f"Checkmate — {winner} wins")
            return True
        if self.board.is_stalemate():
            self.status_text.set("Draw — stalemate")
            return True
        if self.board.is_insufficient_material():
            self.status_text.set("Draw — insufficient material")
            return True
        if self.board.is_seventyfive_moves() or self.board.is_fivefold_repetition():
            self.status_text.set("Draw")
            return True
        return False

    def _refresh_all(self):
        if not self._game_over():
            self.status_text.set(("White" if self.board.turn == chess.WHITE else "Black") + " to move" +
                                 (" · Check" if self.board.is_check() else ""))
        self._draw_board()
        if self.tab.get() == "Play":
            self._render_tab()
        elif self.tab.get() == "Analysis":
            self._render_tab()
        else:
            self._render_tab()


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=PANEL2, background=PANEL2,
                        foreground=TEXT, arrowcolor=TEXT, padding=5)
        style.map("TCombobox", fieldbackground=[("readonly", PANEL2)],
                  foreground=[("readonly", TEXT)])
        style.configure("Treeview", background=PANEL2, fieldbackground=PANEL2,
                        foreground=TEXT, rowheight=28, borderwidth=0)
        style.configure("Treeview.Heading", background="#2C3D4C",
                        foreground=TEXT, font=(FONT, 9, "bold"))
    except tk.TclError:
        pass
    ChessMindApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
