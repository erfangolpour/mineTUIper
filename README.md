# mineTUIper

mineTUIper is a terminal-based Minesweeper game that can be played using keyboard controls. It also includes an analyzer for solving and analyzing Minesweeper boards. The game is implemented in Python using the `rich` library for the terminal interface.

## Features

- **Game**: Play Minesweeper in the terminal with keyboard controls.
- **Solver**: Automatically solve Minesweeper boards using logical deductions.
- **Analyzer**: Analyze Minesweeper boards to generate deterministic boards.

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/erfangolpour/Minesweeper-tui.git
    cd Minesweeper-tui
    ```
2. Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

### Playing the Game

To start the game, run:
```bash
python minesweeper.py
```

Optional arguments:
- `-r`, `--rows`: Number of rows in the board (default: 19)
- `-c`, `--cols`: Number of columns in the board (default: 32)
- `-m`, `--mines`: Percentage of mines in the board (default: 0.25)
- `-s`, `--seed`: Seed for randomness (default: None)
- `-g`, `--guess-allowed`: Disable no-guessing mode (default: False)

### Analyzer

To analyze Minesweeper boards, run:
```bash
python analyzer.py
```

Optional arguments:
- `-r`, `--rows`: Number of rows in the board (default: 10)
- `-c`, `--cols`: Number of columns in the board (default: 10)
- `-m`, `--mines`: Percentage of mines in the board (default: 0.25)
- `-s`, `--seed`: Seed for randomness (default: None)
- `-n`, `--no-guessing`: Enable no-guessing mode (default: False)
- `-d`, `--debug`: Enable debug mode (default: False)

## Controls

- **Reveal**: Press the letter corresponding to the cell.
- **Flag**: Press `Shift` + letter.
- **Reset**: Press `Enter`.
- **Exit**: Press `Esc`.

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
