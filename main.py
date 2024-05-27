# Minesweeper TUI game with Keyboard controls

import argparse
import sys
import termios
import tty
from random import sample
from typing import Dict, Set, Tuple

from rich.align import Align
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class Cell:
    def __init__(self, row: int, col: int):
        self.row = row
        self.col = col
        self.value = 0  # -1 for mine
        self.revealed = False
        self.flagged = False
        self.trigger: str | None = None

    def reveal(self):
        self.revealed = True

    def toggle_flag(self):
        self.flagged = not self.flagged

    def set_trigger(self, trigger: str | None):
        self.trigger = trigger

    @property
    def is_mine(self) -> bool:
        return self.value == -1

    @property
    def display(self) -> Text:
        # Color text based on value
        color_map = [
            "default",  # 0
            "blue",  # 1
            "green",  # 2
            "red",  # 3
            "cyan",  # 4
            "yellow3",  # 5
            "magenta",  # 6
            "purple",  # 7
            "red",  # 8
            "red3",  # mine
        ]
        text = Text(
            (
                ("*" if self.is_mine else str(self.value or "-"))
                if self.revealed
                else "?"
                if self.flagged
                else self.trigger or " "
            ),
            style=(
                color_map[self.value]
                if self.revealed
                else (
                    "yellow"
                    if self.trigger is not None
                    else "red3"
                    if self.flagged
                    else "default"
                )
            ),
        )
        return text

    def __repr__(self):
        return f"Cell({self.row}, {self.col})"


class Board:
    def __init__(self, rows: int, cols: int, mines: int):
        # properties
        self.rows = rows
        self.cols = cols
        # stats
        self.mines = mines  # total number of mines
        self.unflagged = mines  # number of remaining (unflagged) mines
        # board
        self.board = [[Cell(i, j) for j in range(cols)] for i in range(rows)]
        self.unrevealed = {(i, j) for i in range(rows) for j in range(cols)}
        # triggers
        self.triggers = set("abcdefghijklmnopqrstuvwxyz")
        self.mapping: Dict[str, Tuple[int, int]] = dict()  # Currently assigned triggers
        self.potential_cells: Set[Tuple[int, int]] = (
            set()
        )  # Cells in queue for a trigger

        self.place_mines()
        self.find_initial_cell()
        self.assign_triggers()

    def find_initial_cell(self):
        non_mine = None
        # Try to choose a cell that will conveniently expand
        for row, col in self.unrevealed:
            if self.board[row][col].value == 0:
                self.potential_cells.add((row, col))
                break
            elif non_mine is None and not self.board[row][col].is_mine:
                non_mine = (row, col)
        else:
            # Try to choose a non-mine cell
            if non_mine is not None:
                self.potential_cells.add(non_mine)
            else:
                # The board is 100% mines
                self.potential_cells.add((0, 0))

    def place_mines(self):
        for row, col in sample(list(self.unrevealed), self.mines):
            self.board[row][col].value = -1
            # Assign numbers to surrounding cells
            for x in range(max(0, row - 1), min(self.rows, row + 2)):
                for y in range(max(0, col - 1), min(self.cols, col + 2)):
                    if not self.board[x][y].is_mine:
                        self.board[x][y].value += 1

    def assign_triggers(self):
        free_cells = self.potential_cells - set(self.mapping.values())

        for trigger in self.triggers:
            if not free_cells:
                break
            if trigger not in self.mapping:
                row, col = free_cells.pop()  # relies on randomness of sets in Python
                self.mapping[trigger] = (row, col)
                self.board[row][col].set_trigger(trigger)

        if not self.potential_cells:
            # if extra triggers remain, borrow unrevealed cells
            unrevealed_cells = iter(self.unrevealed)
            for trigger in self.triggers - set(self.mapping.keys()):
                try:
                    row, col = next(unrevealed_cells)
                    self.mapping[trigger] = (row, col)
                    self.board[row][col].set_trigger(trigger)
                except StopIteration:
                    # no unrevealed cells remain
                    break

    def display_board(self):
        table = Table(show_header=False, show_lines=True)
        for i in range(self.rows):
            table.add_row(*[cell.display for cell in self.board[i]])
        return table

    def reveal_cell(self, trigger: str) -> bool:
        def expand(row: int, col: int):
            self.board[row][col].reveal()
            self.unrevealed.discard((row, col))
            self.potential_cells.discard((row, col))
            if (trigger := self.board[row][col].trigger) is not None:
                self.mapping.pop(trigger)
                self.board[row][col].set_trigger(None)

            for x in range(max(0, row - 1), min(self.rows, row + 2)):
                for y in range(max(0, col - 1), min(self.cols, col + 2)):
                    if not self.board[x][y].revealed:
                        if self.board[row][col].value == 0:
                            expand(x, y)
                        elif not self.board[x][y].flagged:
                            self.potential_cells.add((x, y))

        row, col = self.mapping[trigger]
        cell = self.board[row][col]
        if cell.is_mine:
            return True

        expand(row, col)
        self.assign_triggers()
        return False

    def flag(self, trigger: str):
        row, col = self.mapping[trigger]
        self.board[row][col].toggle_flag()
        self.board[row][col].set_trigger(None)
        self.potential_cells.discard((row, col))
        self.mapping.pop(trigger)
        self.unflagged -= 1
        self.assign_triggers()

    def reveal_all(self):
        for i, j in self.unrevealed:
            self.board[i][j].revealed = True

    def unflag_all(self):
        for row, col in self.unrevealed:
            if self.board[row][col].flagged:
                self.board[row][col].toggle_flag()
                self.potential_cells.add((row, col))
        self.unflagged = self.mines
        self.assign_triggers()

    def check_win(self) -> bool:
        for i, j in self.unrevealed:
            if not self.board[i][j].is_mine:
                return False
        return True


class Minesweeper:
    def __init__(self, rows: int, cols: int, mines: int):
        self.board = Board(rows, cols, mines)

    def getch(self) -> str:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            return sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    def get_panel(self, text: str) -> Align:
        return Align.center(
            Panel(
                self.board.display_board(),
                title=f"Minesweeper - {self.board.unflagged} mines",
                subtitle=text,
            )
        )

    def play(self):
        with Live(
            self.get_panel("Begin by choosing the initial cell"),
            auto_refresh=False,
            screen=True,
        ) as live:

            def update_board(msg: str = ""):
                live.update(self.get_panel(msg), refresh=True)

            while True:
                choice = self.getch()

                # Escape to exit
                if choice == "\x1b":
                    sys.exit()
                # Enter key to randomize triggers
                if choice == "\r":
                    for trigger in self.board.mapping:
                        row, col = self.board.mapping[trigger]
                        self.board.board[row][col].set_trigger(None)
                    self.board.mapping.clear()
                    self.board.assign_triggers()
                # Backspace to unflag all cells
                elif choice == "\x7f":
                    self.board.unflag_all()
                elif choice.lower() in self.board.mapping:
                    # if upper case letter is pressed, toggle flag
                    if choice.isupper():
                        self.board.flag(choice.lower())
                    else:
                        if self.board.reveal_cell(choice):
                            # player hit a mine
                            self.board.reveal_all()
                            update_board("[red]Game Over! You hit a mine!")
                            break
                        elif self.board.check_win():
                            # the board is cleared
                            update_board("[green]You win!")
                            break
                update_board()

            # wait for key before quitting the game
            self.getch()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-r",
        "--rows",
        type=int,
        default=10,
        help="Number of rows in the board",
    )
    parser.add_argument(
        "-c",
        "--cols",
        type=int,
        default=10,
        help="Number of columns in the board",
    )
    parser.add_argument(
        "-m",
        "--mines",
        type=float,
        default=0.15,
        help="Percentage of mines in the board",
    )
    args = parser.parse_args()

    assert args.rows > 0, "Number of rows must a positive non-zero integer"
    assert args.cols > 0, "Number of columns must be a positive non-zero integer"
    assert (
        0 <= args.mines <= 1
    ), "Percentage of mines must a decimal number between 0 and 1"

    mines = int(args.rows * args.cols * args.mines)
    game = Minesweeper(args.rows, args.cols, mines)
    game.play()
