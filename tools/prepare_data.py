"""运行旧版归档准备入口。 / Run the backward-compatible archive preparation entry point."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from connaught.cli import main as connaught_main


def main():
    connaught_main(["prepare", *sys.argv[1:]], default_root=ROOT)


if __name__ == "__main__":
    main()
