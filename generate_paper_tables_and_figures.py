from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from covert_collusive_hotpot.generate_paper_assets import main


if __name__ == "__main__":
    main()
