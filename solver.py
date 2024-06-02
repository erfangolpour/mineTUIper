from collections import defaultdict
from itertools import combinations as iter_combinations
from random import choice as rand_choice
from typing import Dict, Iterable, Sequence, Set, Tuple

from board import Board, Cell


def get_combinations(lst: Set) -> Iterable[Tuple]:
    combinations = []
    for r in range(1, len(lst) + 1):
        combinations.extend(iter_combinations(lst, r))
    return combinations


class Tile:
    """
    A collection of cells in a superposition.
    The existence of a mine is known within the tile, but not its location.
    """

    def __init__(self, cells: Set[Cell], n_mine: int):
        self.cells = cells
        self.mines = n_mine

    @property
    def mine_perc(self) -> float:
        # NOTE: we assume self.cells is never empty based on prior checks
        return self.mines / len(self.cells)


class Solver:
    def __init__(self, board: Board):
        self.board = board
        self.tiles: Sequence[Tile] = []
        self.tile_map: Dict[Cell, Set[Tile]] = defaultdict(set)

    def solve(self) -> bool:
        while self.propagate_known_values():
            continue
        return self.board.check_win()

    def get_neighbour_tiles(self, cells: Set[Cell]) -> Set[Tile]:
        """return any tile that has a cell in common with the given cells"""
        return {tile for neighbour in cells for tile in self.tile_map[neighbour]}

    def propagate_known_values(self) -> bool:
        to_reveal: Set[Cell] = set()
        to_flag: Set[Cell] = set()

        # Generate tiles naively
        self.tiles = []
        self.tile_map.clear()
        for cell in self.board.revealed:
            neighbours = self.board.get_neighbour_cells(cell)
            if unknown_neighbours := {n for n in neighbours if not n.known}:
                tile = Tile(unknown_neighbours, cell.mines - cell.flags)
                for neighbour in unknown_neighbours:
                    self.tile_map[neighbour].add(tile)
                self.tiles.append(tile)

        # Refactor tiles:
        # This will effectively subtract subtiles from larger tiles, dividing
        # them into their building blocks. This can greatly assist the logic engine
        changes = True
        while changes:
            changes = False
            new_tiles: Sequence[Tile] = []
            refactored_tiles: Dict[Cell, Set[Tile]] = defaultdict(set)
            for tile in self.tiles:
                if tile.mine_perc == 0:
                    # trivial: all cells are safe
                    to_reveal |= tile.cells
                elif tile.mine_perc == 1:
                    # trivial: every cell is a mine
                    to_flag |= tile.cells
                else:
                    # remove any neighbour tile contained within this tile from it
                    for neighbour_tile in self.get_neighbour_tiles(tile.cells):
                        if neighbour_tile.cells < tile.cells:
                            tile.mines -= neighbour_tile.mines
                            tile.cells -= neighbour_tile.cells
                            changes = True

                    if tile.cells:
                        for cell in tile.cells:
                            refactored_tiles[cell].add(tile)
                        new_tiles.append(tile)

            self.tiles = new_tiles
            self.tile_map = refactored_tiles

        for cell in self.board.revealed:
            if unknown_neighbours := {
                n for n in self.board.get_neighbour_cells(cell) if not n.known
            }:
                tile_combinations = get_combinations(
                    self.get_neighbour_tiles(unknown_neighbours)
                )

                def get_common_cells(
                    tiles: Sequence[Tile],
                ) -> Set[Cell]:
                    common_cells: Set[Cell] = set()
                    for i in range(len(tiles) - 1):
                        for j in range(i + 1, len(tiles)):
                            common_cells |= tiles[i].cells & tiles[j].cells
                    return common_cells

                # avoid overlapping tile combinations
                for tile_comb in {
                    tile_comb
                    for tile_comb in tile_combinations
                    if not get_common_cells(tile_comb)
                }:
                    tile_comb_mines = sum(tile.mines for tile in tile_comb)
                    tile_comb_cells = {
                        cell for tile in tile_comb for cell in tile.cells
                    }
                    # if the tile permits less mines than the cell needs
                    # and the remaining neighbours are just enough to satisfy
                    # the difference, the remaining neighbours are mines
                    if (
                        tile_comb_mines < cell.mines - cell.flags
                        and len(unknown_neighbours - tile_comb_cells)
                        == cell.mines - cell.flags - tile_comb_mines
                    ):
                        to_flag |= unknown_neighbours - tile_comb_cells
                    # if the mines introduced by the tile are contained by
                    # the cell's neighbourhood AND satisfy the cell, the
                    # remaining neighbours are safe
                    elif (
                        tile_comb_cells < unknown_neighbours
                        and tile_comb_mines == cell.mines - cell.flags
                    ):
                        to_reveal |= unknown_neighbours - tile_comb_cells

        if len(to_reveal) == 0 and len(to_flag) == 0:
            # final checks based on the number of unflagged mines
            if unknown_cells := self.board.unrevealed - self.board.flagged:
                if not self.board.unflagged:
                    # all mines are flagged, remaining cells are safe
                    to_reveal |= unknown_cells
                elif len(unknown_cells) == self.board.unflagged:
                    # all remaining cells must be mines
                    to_flag |= unknown_cells
                else:
                    # if one tile alone can satisfy the board, any other cell is safe
                    for tile in self.get_neighbour_tiles(unknown_cells):
                        if tile.mines == self.board.unflagged:
                            to_reveal |= unknown_cells - tile.cells
                    if not to_reveal:
                        return False  # no advancement could be made
            else:
                return False  # the board is solved

        for cell in to_reveal:
            self.board.reveal_cell(cell)

        for cell in to_flag:
            self.board.flag_cell(cell)

        return True

    def make_guess(self) -> Cell:
        # if forced, choose a random cell from a tile with least mine percentage
        best_tile = self.tiles[0]
        untiled_mines = self.board.unflagged
        untiled_cells = self.board.unrevealed - self.board.flagged
        for tile in self.tiles:
            untiled_cells -= tile.cells
            untiled_mines -= tile.mines
            if tile.mine_perc < best_tile.mine_perc:
                best_tile = tile

        if best_tile.mine_perc > untiled_mines / len(untiled_cells):
            # it is safer to choose a cell from untiled territory
            return rand_choice(list(untiled_cells))
        return rand_choice(list(best_tile.cells))
