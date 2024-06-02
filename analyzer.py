# Minesweeper TUI game with Keyboard controls

import argparse
import sys
import termios
import tty
from random import choice as rand_choice
from random import seed as set_seed

from rich.align import Align
from rich.live import Live
from rich.panel import Panel

from board import Board
from solver import Solver


class Analyzer:
    def __init__(
        self, rows: int, cols: int, mines: int, debug: bool, no_guessing: bool
    ):
        self.rows = rows
        self.cols = cols
        self.mines = mines
        self.debug = debug
        self.no_guessing = no_guessing

    def getch(self) -> str:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def get_panel(self, board, text: str, num_board: int) -> Align:
        return Align.center(
            Panel(
                board.display_board(),
                title=f"Minesweeper | {board.unflagged} mines | Board #{num_board}",
                subtitle=text,
            )
        )

    def analyze(self):
        num_board = 1
        board = Board(self.rows, self.cols, self.mines)
        # always choose top-left corner as the initial cell
        init_cell = board.board[0][0]  # or rand_choice(self.cells) for random choice
        board.place_mines(
            board.unrevealed - {init_cell} - board.get_neighbour_cells(init_cell),
            board.unflagged,
        )
        board.reveal_cell(init_cell)
        solver = Solver(board)
        with Live(
            self.get_panel(board, "Board initialized", num_board),
            auto_refresh=False,
            screen=True,
        ) as live:

            def update_board(msg: str = ""):
                live.update(
                    self.get_panel(board, msg, num_board),
                    refresh=True,
                )

            def debug_report(msg: str = ""):
                if self.debug:
                    update_board(msg)
                    self.getch()

            while True:
                skip = False
                cur_step = 0
                while solver.propagate_known_values():
                    if self.debug and not skip:
                        update_board(
                            f"Step: {cur_step} | Enter: Skip - Space: Continue - Esc: Quit"
                        )
                        choice = self.getch()

                        # Escape to exit
                        if choice == "\x1b":
                            sys.exit()
                        # Space to skip
                        elif choice == "\r":
                            skip = True

                    cur_step += 1

                if board.check_win():
                    update_board(
                        "Deterministic board generated. Attempting to verify..."
                    )
                    self.getch()
                    break
                elif self.no_guessing:
                    debug_report("[red]The solver cannot advance. Finding a remedy...")

                    unknown_cells = board.unrevealed - board.flagged
                    neighbour_cells = {
                        neighbour
                        for cell in unknown_cells
                        for neighbour in board.get_neighbour_cells(cell)
                    }
                    if not neighbour_cells & board.revealed:
                        # mines are surrounded by flags, remove a random flag
                        # to allow advancement (forces higher mine density)
                        cell = rand_choice(
                            [cell for cell in neighbour_cells if cell.flagged]
                        )
                        board.unflag_cell(cell)
                        cell.is_mine = False
                        for neighbour in board.get_neighbour_cells(cell):
                            neighbour.mines -= 1
                        board.place_mines(
                            unknown_cells, board.unflagged
                        )  # relocate the removed mine

                        # NOTE: Relocating flags can generate undeterministic
                        # boards by assuming the solver had no prior knowledge
                        # of the existence of the mine removed, which is generally
                        # not true. Consequently, the solver must start solving
                        # the board from scratch to ensure the board is in fact solvable.
                        board.reset()
                        board.reveal_cell(init_cell)

                        debug_report(
                            "Mine wall detected. Flag got removed. Re-solving..."
                        )
                    elif len(unknown_cells) == board.unflagged + 1:
                        # the board is unsolvable, reinitialize
                        board = Board(self.rows, self.cols, self.mines)
                        board.place_mines(
                            board.unrevealed
                            - {init_cell}
                            - board.get_neighbour_cells(init_cell),
                            board.unflagged,
                        )
                        board.reveal_cell(init_cell)
                        solver = Solver(board)
                        num_board += 1
                        debug_report("The board was unsolvable. Reinitialized.")
                    else:
                        # rearrange mines around the revealed/flagged cells
                        # NOTE: Rearranging mines may remove all mines around a previously
                        # revealed cell. Such cell should have caused a cascade effect.
                        # We could re-reveal these cells to cause the cascade. However,
                        # in practice, this is not necessary as the solver seems to
                        # advances regardless when this occurs.
                        board.place_mines(
                            board.unrevealed - board.flagged, board.unflagged
                        )
                        debug_report("Surrounding mines rearranged.")
                else:
                    # guessing is allowed
                    debug_report("The solver cannot advance. Making a guess...")
                    best_guess = solver.make_guess()
                    board.reveal_cell(best_guess)
                    if best_guess.is_mine:
                        update_board("[red]Best guess was a mine. Reinitialized...")
                        self.getch()

                        board = Board(self.rows, self.cols, self.mines)
                        board.place_mines(
                            board.unrevealed
                            - {init_cell}
                            - board.get_neighbour_cells(init_cell),
                            board.unflagged,
                        )
                        board.reveal_cell(init_cell)
                        solver = Solver(board)
                        num_board += 1

                update_board("Working...")

            # wait for key before quitting
            # re-solve:
            board.reset()
            board.reveal_cell(init_cell)
            skip = False
            cur_step = 0
            while solver.propagate_known_values():
                if self.debug and not skip:
                    update_board(
                        f"Step: {cur_step} | Enter: Skip - Space: Continue - Esc: Quit"
                    )
                    choice = self.getch()

                    # Escape to exit
                    if choice == "\x1b":
                        sys.exit()
                    # Space to skip
                    elif choice == "\r":
                        skip = True

                cur_step += 1

            update_board("[green]Deterministic board generated and verified.")
            self.getch()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-r",
        "--rows",
        type=int,
        default=10,
        help="number of rows in the board",
    )
    parser.add_argument(
        "-c",
        "--cols",
        type=int,
        default=10,
        help="number of columns in the board",
    )
    parser.add_argument(
        "-m",
        "--mines",
        type=float,
        default=0.25,
        help="percentage of mines in the board",
    )
    parser.add_argument(
        "-s",
        "--seed",
        type=int,
        default=None,
        help="seed for the randomness",
    )
    parser.add_argument(
        "-n",
        "--no-guessing",
        help="enable no-guessing mode",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "-d",
        "--debug",
        help="should the solver wait when faced with difficulty or continue silently",
        default=False,
        action="store_true",
    )
    args = parser.parse_args()

    assert args.rows > 0, "Number of rows must be a positive non-zero integer"
    assert args.cols > 0, "Number of columns must be a positive non-zero integer"
    assert (
        0 <= args.mines <= 1
    ), "Percentage of mines must be a decimal number between 0 and 1"

    set_seed(args.seed)
    mines = int(args.rows * args.cols * args.mines)
    analyzer = Analyzer(args.rows, args.cols, mines, args.debug, args.no_guessing)
    analyzer.analyze()
