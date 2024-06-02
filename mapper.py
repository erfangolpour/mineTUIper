from random import choice as rand_choice
from random import shuffle
from typing import Dict, Set

from board import Board, Cell
from solver import Solver


class MappedBoard(Board):
    def __init__(self, rows: int, cols: int, mines: int, no_guessing: bool):
        super().__init__(rows, cols, mines)
        # triggers
        self.no_guessing = no_guessing
        self.init_cell: Cell | None = None
        self.mapper = Mapper(self, set("abcdefghijklmnopqrstuvwxyz"))
        self.mapper.assign_triggers()  # assign triggers to allow for initial choice

    def get_neighbour_cells(self, cell) -> Set[Cell]:
        return {
            self.board[i][j]
            for i in range(max(0, cell.row - 1), min(self.rows, cell.row + 2))
            for j in range(max(0, cell.col - 1), min(self.cols, cell.col + 2))
            if i != cell.row or j != cell.col
        }

    def reveal_cell(self, cell: Cell):
        def expand(cell: Cell):
            cell.reveal()
            self.revealed.add(cell)
            self.unrevealed.discard(cell)
            self.mapper.queue.discard(cell)
            self.mapper.unmap(cell)

            for neighbour in filter(
                lambda c: not c.revealed, self.get_neighbour_cells(cell)
            ):
                if cell.mines == 0:
                    expand(neighbour)
                elif not neighbour.flagged:
                    self.mapper.queue.add(neighbour)

        if self.init_cell is None:
            self.init_cell = cell

            # place mines before the first cell is revealed
            self.place_mines(
                self.unrevealed
                - {self.init_cell}
                - self.get_neighbour_cells(self.init_cell),
                self.unflagged,
            )

            # reveal inital cell
            expand(self.init_cell)

            if self.no_guessing:
                solver = Solver(self)
                while True:
                    if solver.solve():
                        # Board is deterministic
                        self.reset()
                        expand(self.init_cell)
                        break
                    else:
                        unknown_cells = self.unrevealed - self.flagged
                        neighbour_cells = {
                            neighbour
                            for cell in unknown_cells
                            for neighbour in self.get_neighbour_cells(cell)
                        }
                        if not neighbour_cells & self.revealed:
                            # mines are surrounded by flags, remove a random flag
                            # to allow advancement (forces higher mine density)
                            rand_flag = rand_choice(
                                [cell for cell in neighbour_cells if cell.flagged]
                            )
                            self.unflag_cell(rand_flag)
                            rand_flag.is_mine = False
                            for neighbour in self.get_neighbour_cells(rand_flag):
                                neighbour.mines -= 1
                            self.place_mines(
                                unknown_cells, self.unflagged
                            )  # relocate the removed mine

                            # NOTE: Relocating flags can generate undeterministic
                            # boards by assuming the solver had no prior knowledge
                            # of the existence of the mine removed, which is generally
                            # not true. Consequently, the solver must start solving
                            # the board from scratch to ensure the board is in fact solvable.
                            self.reset()
                            expand(self.init_cell)
                        elif len(unknown_cells) == self.unflagged + 1:
                            # the board is unsolvable, reinitialize
                            # reset cells
                            for cell in filter(lambda c: c.is_mine, self.unrevealed):
                                cell.is_mine = False
                                for neighbour in self.get_neighbour_cells(cell):
                                    neighbour.mines -= 1
                            self.reset()
                            # generate mines
                            self.place_mines(
                                self.unrevealed
                                - {self.init_cell}
                                - self.get_neighbour_cells(self.init_cell),
                                self.unflagged,
                            )
                            expand(self.init_cell)
                        else:
                            # rearrange mines around the revealed/flagged cells
                            # NOTE: Rearranging mines may remove all mines around a previously
                            # revealed cell. Such cell should have caused a cascade effect.
                            # We could re-reveal these cells to cause the cascade. However,
                            # in practice, this is not necessary as the solver seems to
                            # advances regardless when this occurs.
                            self.place_mines(
                                self.unrevealed - self.flagged, self.unflagged
                            )

            # reset triggers after initial cell is chosen
            self.mapper.reset()
            self.mapper.assign_triggers()
        else:
            expand(cell)
            self.mapper.assign_triggers()

    def flag_cell(self, cell: Cell):
        super().flag_cell(cell)
        self.mapper.queue.discard(cell)
        self.mapper.unmap(cell)
        self.mapper.assign_triggers()

    def unflag_all(self):
        for cell in self.flagged:
            self.unflag_cell(cell)
            self.mapper.queue.add(cell)
        self.mapper.assign_triggers()


class Mapper:
    def __init__(self, board: MappedBoard, triggers: Set[str]):
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
