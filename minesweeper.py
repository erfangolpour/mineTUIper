# Minesweeper TUI game with Keyboard controls

import argparse
import sys
import os

from rich.align import Align
from rich.live import Live
from rich.panel import Panel

from mapper import MappedBoard

if os.name == "nt":
    import msvcrt
else:
    import tty
    import termios

class Minesweeper:
    def __init__(self, board: MappedBoard):
        self.board = board

    def getch(self) -> str:
        if os.name == "nt":
            return msvcrt.getch().decode("utf-8")
        
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
                title=f"Minesweeper | {self.board.unflagged} mines",
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
                update_board("Key: Reveal - Shift + Key: Flag - ?: Help")
                choice = self.getch()

                # Escape to exit
                if choice == "\x1b":
                    sys.exit()
                # Enter key to randomize triggers
                elif choice == "\r":
                    self.board.mapper.reset()
                    self.board.mapper.assign_triggers()
                # Backspace to remap all flags
                elif choice == "\x7f":
                    self.board.remap_flags()
                elif choice.lower() in self.board.mapper.mapping:
                    # if upper case letter is pressed, toggle flag
                    if choice.isupper():
                        self.board.flag_cell(self.board.mapper.mapping[choice.lower()])
                    else:
                        cell = self.board.mapper.mapping[choice]
                        if cell.is_mine:
                            # player hit a mine
                            self.board.reveal_all()
                            update_board("[red]Game Over. You hit a mine.")
                            break
                        else:
                            self.board.reveal_cell(cell)
                            if self.board.check_win():
                                # the board is cleared
                                update_board("[green]Marvellous! You win!")
                                break

            # wait for key before quitting the game
            self.getch()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-r",
        "--rows",
        type=int,
        default=19,
        help="number of rows in the board",
    )
    parser.add_argument(
        "-c",
        "--cols",
        type=int,
        default=32,
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
        "-g",
        "--guess-allowed",
        help="disable no-guessing mode",
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
    board = MappedBoard(args.rows, args.cols, mines, not args.guess_allowed)
    game = Minesweeper(board)
    game.play()
