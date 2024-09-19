from random import sample
from typing import Set

from rich.table import Table
from rich.text import Text


class Cell:
    def __init__(self, row: int, col: int):
        # location
        self.row = row
        self.col = col
        # mines/flag
        self.mines = 0  # number of mines in the neighbourhood
        self.flags = 0  # number of flags in the neighbourhood
        # states
        self.is_mine = False
        self.revealed = False
        self.flagged = False
        self.known = False
        # trigger
        self.trigger: str | None = None

    def reveal(self):
        self.known = True
        self.revealed = True

    def hide(self):
        self.known = False
        self.revealed = False

    def flag(self):
        self.known = True
        self.flagged = True

    def unflag(self):
        self.known = False
        self.flagged = False

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
            "magenta",  # 4
            "dark_red",  # 5
            "cyan",  # 6
            "purple",  # 7
            "bright_black",  # 8
        ]
        text = Text(
            (
                ("*" if self.is_mine else str(self.mines or "-"))
                if self.revealed
                else "?" if self.flagged else self.trigger or " "
            ),
            style=(
                ("red3" if self.is_mine else color_map[self.mines])
                if self.revealed
                else (
                    "yellow"
                    if self.trigger is not None
                    else "red3" if self.flagged else "default"
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
        self.unflagged = mines  # number of remaining (unflagged) mines
        # board
        self.board = [[Cell(i, j) for j in range(cols)] for i in range(rows)]
        self.cells = [cell for row in self.board for cell in row]
        self.revealed: Set[Cell] = set()
        self.unrevealed = {cell for row in self.board for cell in row}
        self.flagged: Set[Cell] = set()

    def get_neighbour_cells(self, cell) -> Set[Cell]:
        return {
            self.board[i][j]
            for i in range(max(0, cell.row - 1), min(self.rows, cell.row + 2))
            for j in range(max(0, cell.col - 1), min(self.cols, cell.col + 2))
            if i != cell.row or j != cell.col
        }

    def place_mines(self, perimeter: Set[Cell], n_mines: int):
        # only alter cells within the given perimeter
        cells = [cell for cell in self.cells if cell in perimeter]

        # reset cells
        for cell in filter(lambda c: c.is_mine, cells):
            cell.is_mine = False
            for neighbour in self.get_neighbour_cells(cell):
                neighbour.mines -= 1

        # take a random sample and place new mines
        for cell in sample(cells, n_mines):
            cell.is_mine = True
            # Assign numbers to surrounding cells
            for neighbour in self.get_neighbour_cells(cell):
                neighbour.mines += 1

    def reveal_cell(self, cell: Cell):
        cell.reveal()
        self.revealed.add(cell)
        self.unrevealed.discard(cell)

        if cell.mines == 0:
            for neighbour in filter(
                lambda c: not c.revealed, self.get_neighbour_cells(cell)
            ):
                self.reveal_cell(neighbour)

    def hide(self, cell: Cell):
        cell.hide()
        self.revealed.discard(cell)
        self.unrevealed.add(cell)

    def hide_all(self):
        for cell in self.revealed:
            cell.hide()
        self.unrevealed |= self.revealed
        self.revealed.clear()

    def reveal_all(self):
        for cell in self.unrevealed:
            self.revealed.add(cell)
            cell.reveal()
        self.unrevealed.clear()

    def flag_cell(self, cell: Cell):
        cell.flag()
        self.flagged.add(cell)
        self.unflagged -= 1
        for cell in self.get_neighbour_cells(cell):
            cell.flags += 1

    def unflag_cell(self, cell: Cell):
        cell.unflag()
        for neighbour in self.get_neighbour_cells(cell):
            neighbour.flags -= 1
        self.unflagged += 1
        self.flagged.discard(cell)

    def unflag_all(self):
        for cell in self.flagged:
            cell.unflag()
            for neighbour in self.get_neighbour_cells(cell):
                neighbour.flags -= 1
        self.unflagged += len(self.flagged)
        self.flagged.clear()

    def reset(self):
        self.hide_all()
        self.unflag_all()

    def display_board(self):
        table = Table(show_header=False, show_lines=True)
        for i in range(self.rows):
            table.add_row(*[cell.display for cell in self.board[i]])
        return table

    def check_win(self) -> bool:
        return all(cell.is_mine for cell in self.unrevealed)
