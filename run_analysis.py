"""运行旧版分析入口。 / Run the backward-compatible analysis entry point."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
from connaught.cli import main as connaught_main


def main():
    connaught_main(["run", *sys.argv[1:]], default_root=ROOT)


if __name__ == "__main__":
    main()
