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


class Cluster:
    """
    An undeterministic collection of cells.
    The existence of a mine is known within the cluster, but not its location.
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
        self.clusters: Sequence[Cluster] = []
        self.cluster_map: Dict[Cell, Set[Cluster]] = defaultdict(set)

    def solve(self) -> bool:
        while self.propagate_known_values():
            continue
        return self.board.check_win()

    def get_neighbour_clusters(self, cells: Set[Cell]) -> Set[Cluster]:
        """return any cluster that has a cell in common with the given cells"""
        return {
            cluster for neighbour in cells for cluster in self.cluster_map[neighbour]
        }

    def propagate_known_values(self) -> bool:
        to_reveal: Set[Cell] = set()
        to_flag: Set[Cell] = set()

        # Generate clusters naively
        self.clusters = []
        self.cluster_map.clear()
        for cell in self.board.revealed:
            neighbours = self.board.get_neighbour_cells(cell)
            if unknown_neighbours := {n for n in neighbours if not n.known}:
                cluster = Cluster(unknown_neighbours, cell.mines - cell.flags)
                for neighbour in unknown_neighbours:
                    self.cluster_map[neighbour].add(cluster)
                self.clusters.append(cluster)

        # Refactor clusters:
        # This will effectively subtract subclusters from larger clusters, dividing
        # them into their building blocks. This can greatly assist the logic engine
        changes = True
        while changes:
            changes = False
            new_clusters: Sequence[Cluster] = []
            refactored_clusters: Dict[Cell, Set[Cluster]] = defaultdict(set)
            for cluster in self.clusters:
                if cluster.mine_perc == 0:
                    # trivial: all cells are safe
                    to_reveal |= cluster.cells
                elif cluster.mine_perc == 1:
                    # trivial: every cell is a mine
                    to_flag |= cluster.cells
                else:
                    # remove any neighbour cluster contained within this cluster from it
                    for neighbour_cluster in self.get_neighbour_clusters(cluster.cells):
                        if neighbour_cluster.cells < cluster.cells:
                            cluster.mines -= neighbour_cluster.mines
                            cluster.cells -= neighbour_cluster.cells
                            changes = True

                    if cluster.cells:
                        for cell in cluster.cells:
                            refactored_clusters[cell].add(cluster)
                        new_clusters.append(cluster)

            self.clusters = new_clusters
            self.cluster_map = refactored_clusters

        for cell in self.board.revealed:
            if unknown_neighbours := {
                n for n in self.board.get_neighbour_cells(cell) if not n.known
            }:
                cluster_combinations = get_combinations(
                    self.get_neighbour_clusters(unknown_neighbours)
                )

                def get_common_cells(
                    clusters: Sequence[Cluster],
                ) -> Set[Cell]:
                    common_cells: Set[Cell] = set()
                    for i in range(len(clusters) - 1):
                        for j in range(i + 1, len(clusters)):
                            common_cells |= clusters[i].cells & clusters[j].cells
                    return common_cells

                # avoid overlapping cluster combinations
                for cluster_comb in {
                    cluster_comb
                    for cluster_comb in cluster_combinations
                    if not get_common_cells(cluster_comb)
                }:
                    cluster_comb_mines = sum(cluster.mines for cluster in cluster_comb)
                    cluster_comb_cells = {
                        cell for cluster in cluster_comb for cell in cluster.cells
                    }
                    # if the cluster permits less mines than the cell needs
                    # and the remaining neighbours are just enough to satisfy
                    # the difference, the remaining neighbours are mines
                    if (
                        cluster_comb_mines < cell.mines - cell.flags
                        and len(unknown_neighbours - cluster_comb_cells)
                        == cell.mines - cell.flags - cluster_comb_mines
                    ):
                        to_flag |= unknown_neighbours - cluster_comb_cells
                    # if the mines introduced by the cluster are contained by
                    # the cell's neighbourhood AND satisfy the cell, the
                    # remaining neighbours are safe
                    elif (
                        cluster_comb_cells < unknown_neighbours
                        and cluster_comb_mines == cell.mines - cell.flags
                    ):
                        to_reveal |= unknown_neighbours - cluster_comb_cells

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
                    # if clustes can satisfy the board, any other cell is safe
                    if sum(cluster.mines for cluster in self.clusters) == self.board.unflagged:
                        for cluster in self.clusters:
                            unknown_cells -= cluster.cells
                        to_reveal |= unknown_cells
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
        # if forced, choose a random cell from a cluster with least mine percentage
        best_cluster = self.clusters[0]
        unclusterd_mines = self.board.unflagged
        unclusterd_cells = self.board.unrevealed - self.board.flagged
        for cluster in self.clusters:
            unclusterd_cells -= cluster.cells
            unclusterd_mines -= cluster.mines
            if cluster.mine_perc < best_cluster.mine_perc:
                best_cluster = cluster

        if best_cluster.mine_perc > unclusterd_mines / len(unclusterd_cells):
            # it is safer to choose a cell from unclusterd territory
            return rand_choice(list(unclusterd_cells))
        return rand_choice(list(best_cluster.cells))
