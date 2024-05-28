# Minesweeper TUI game with Keyboard controls

import argparse
import sys
import termios
import tty
from random import sample, shuffle
from typing import Dict, Set

from rich.align import Align
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


class Cell:
    def __init__(self, row: int, col: int):
        self.row = row
        self.col = col
        self.value = 0  # number of mines in the neighborhood
        self.is_mine = False
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
                ("red3" if self.is_mine else color_map[self.value])
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


class Mapper:
    def __init__(self, board: "Board", triggers: Set[str]):
        self.board = board
        self.triggers = triggers
        self.mapping: Dict[str, Cell] = dict()  # currently assigned triggers
        self.queue: Set[Cell] = set()  # potential cells for a trigger

    def assign_triggers(self):
        free_triggers = iter(self.triggers - set(self.mapping))

        free_cells = list(self.queue - set(self.mapping.values()))
        shuffle(free_cells)
        for free_cell in free_cells:
            try:
                self.map(free_cell, next(free_triggers))
            except StopIteration:
                # no free triggers
                break

        if not self.queue:
            # if extra triggers remain, borrow unrevealed cells
            free_cells = list(self.board.unrevealed - set(self.mapping.values()))
            shuffle(free_cells)
            for free_cell in free_cells:
                try:
                    self.map(free_cell, next(free_triggers))
                except StopIteration:
                    # no free triggers
                    break

    def map(self, cell: Cell, trigger: str):
        self.mapping[trigger] = cell
        cell.set_trigger(trigger)

    def unmap(self, cell: Cell):
        if (trigger := cell.trigger) is not None:
            self.mapping.pop(trigger)
            cell.set_trigger(None)

    def reset(self):
        for cell in self.mapping.values():
            cell.set_trigger(None)
        self.mapping.clear()


class Board:
    def __init__(self, rows: int, cols: int, mines: int, no_guessing: bool):
        # properties
        self.rows = rows
        self.cols = cols
        self.mines = mines  # total number of mines
        self.no_guessing = no_guessing  # False if guessing is allowed
        # stats
        self.unflagged = mines  # number of remaining (unflagged) mines
        self.init_cell: Cell | None = None  # initial cell chosen by the player
        # board
        self.board = [[Cell(i, j) for j in range(cols)] for i in range(rows)]
        self.unrevealed = {cell for row in self.board for cell in row}
        # triggers
        self.mapper = Mapper(self, set("abcdefghijklmnopqrstuvwxyz"))
        self.mapper.assign_triggers()  # assign triggers to allow for initial choice

    def get_neighbors(self, cell) -> Set[Cell]:
        return {
            self.board[i][j]
            for i in range(max(0, cell.row - 1), min(self.rows, cell.row + 2))
            for j in range(max(0, cell.col - 1), min(self.cols, cell.col + 2))
            if i != cell.row or j != cell.col
        }

    def place_mines(self, init_cell: Cell):
        # don't generate any mines in the eight squares perimeter of the initial cell (single neighbourhood rule)
        perimeter = self.get_neighbors(init_cell) | {init_cell}
        for cell in sample(list(self.unrevealed - perimeter), self.mines):
            cell.is_mine = True
            # Assign numbers to surrounding cells
            for cell in self.get_neighbors(cell):
                cell.value += 1

        if self.no_guessing and not Solver(self).solve():
            self.reset()  # regenerate self.board + self.unrevealed
            self.place_mines(self.board[init_cell.row][init_cell.col])

    def reveal_cell(self, cell: Cell) -> bool:
        def expand(cell: Cell):
            cell.reveal()
            self.unrevealed.discard(cell)
            self.mapper.queue.discard(cell)
            self.mapper.unmap(cell)

            for neighbour in self.get_neighbors(cell):
                if not neighbour.revealed:
                    if cell.value == 0:
                        expand(neighbour)
                    elif not neighbour.flagged:
                        self.mapper.queue.add(neighbour)

        if self.init_cell is None:
            self.init_cell = cell
            # place mines after first cell is revealed
            self.place_mines(cell)
            # reset triggers after initial cell is chosen
            self.mapper.reset()

        if cell.is_mine:
            return True
        expand(cell)
        self.mapper.assign_triggers()
        return False

    def reveal_all(self):
        for cell in self.unrevealed:
            cell.reveal()

    def flag(self, cell: Cell):
        cell.toggle_flag()
        self.mapper.queue.discard(cell)
        self.mapper.unmap(cell)
        self.mapper.assign_triggers()
        self.unflagged -= 1

    def unflag_all(self):
        for cell in self.unrevealed:
            if cell.flagged:
                cell.toggle_flag()
                self.mapper.queue.add(cell)
        self.unflagged = self.mines
        self.mapper.assign_triggers()

    def reset(self):
        self.board = [[Cell(i, j) for j in range(self.cols)] for i in range(self.rows)]
        self.unrevealed = {cell for row in self.board for cell in row}

    def display_board(self):
        table = Table(show_header=False, show_lines=True)
        for i in range(self.rows):
            table.add_row(*[cell.display for cell in self.board[i]])
        return table

    def check_win(self) -> bool:
        for cell in self.unrevealed:
            if not cell.is_mine:
                return False
        return True


class Solver:
    def __init__(self, board: Board):
        # deep-copy the board
        self.board = []
        self.rows = board.rows
        self.cols = board.cols
        self.unrevealed = set()
        self.flagged: Set[Cell] = set()
        self.cells = set()
        for row in board.board:
            row_copy = []
            for cell in row:
                cell_copy = Cell(cell.row, cell.col)
                cell_copy.value = cell.value
                cell_copy.is_mine = cell.is_mine
                if cell.revealed:
                    cell_copy.revealed = True
                else:
                    self.unrevealed.add(cell_copy)
                row_copy.append(cell_copy)
            self.board.append(row_copy)

    def solve(self) -> bool:
        while self.propagate_known_values():
            continue

        if self.unrevealed:
            for cell in self.find_safe_cells():
                self.reveal_cell(cell)

        return not self.unrevealed - self.flagged

    def propagate_known_values(self) -> bool:
        changes = False
        for row in range(self.rows):
            for col in range(self.cols):
                cell = self.board[row][col]
                if cell.revealed and not cell.is_mine:
                    neighbours = self.get_neighbors(cell)
                    revealed_neighbors = {n for n in neighbours if n.revealed}
                    flagged_neighbors = {n for n in neighbours if n.flagged}
                    unrevealed_neighbors = (
                        neighbours - revealed_neighbors - flagged_neighbors
                    )

                    if cell.value == len(flagged_neighbors):
                        for neighbor in unrevealed_neighbors:
                            self.reveal_cell(cell)
                            changes = True
                    elif cell.value == len(revealed_neighbors) + len(flagged_neighbors):
                        for neighbor in unrevealed_neighbors:
                            neighbor.toggle_flag()
                            self.flagged.add(cell)
                            changes = True
        return changes

    def find_safe_cells(self) -> Set[Cell]:
        safe_cells = set()
        for cell in self.unrevealed - self.flagged:
            neighbors = self.get_neighbors(cell)
            revealed_neighbors = {n for n in neighbors if n.revealed}
            flagged_neighbors = {n for n in neighbors if n.flagged}
            if sum(n.value for n in revealed_neighbors) + len(flagged_neighbors) == 0:
                safe_cells.add(cell)
        return safe_cells

    def get_neighbors(self, cell) -> Set[Cell]:
        return {
            self.board[i][j]
            for i in range(max(0, cell.row - 1), min(self.rows, cell.row + 2))
            for j in range(max(0, cell.col - 1), min(self.cols, cell.col + 2))
            if i != cell.row or j != cell.col
        }

    def reveal_cell(self, cell):
        cell.reveal()
        self.unrevealed.discard(cell)

        for neighbour in self.get_neighbors(cell):
            if not neighbour.revealed:
                if cell.value == 0:
                    self.reveal_cell(neighbour)


class Minesweeper:
    def __init__(self, board: Board):
        self.board = board

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
                    self.board.mapper.reset()
                    self.board.mapper.assign_triggers()
                # Backspace to unflag all cells
                elif choice == "\x7f":
                    self.board.unflag_all()
                elif choice.lower() in self.board.mapper.mapping:
                    # if upper case letter is pressed, toggle flag
                    if choice.isupper():
                        self.board.flag(self.board.mapper.mapping[choice.lower()])
                    else:
                        if self.board.reveal_cell(self.board.mapper.mapping[choice]):
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
    parser.add_argument(
        "-n",
        "--no-guessing",
        help="Enable no-guessing mode",
        default=False,
        action="store_true",
    )
    args = parser.parse_args()

    assert args.rows > 0, "Number of rows must a positive non-zero integer"
    assert args.cols > 0, "Number of columns must be a positive non-zero integer"
    assert (
        0 <= args.mines <= 1
    ), "Percentage of mines must a decimal number between 0 and 1"

    mines = int(args.rows * args.cols * args.mines)
    board = Board(args.rows, args.cols, mines, args.no_guessing)
    game = Minesweeper(board)
    game.play()
