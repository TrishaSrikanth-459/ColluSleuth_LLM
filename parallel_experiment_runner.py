from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from covert_collusive_hotpot.run_experiments import main


if __name__ == "__main__":
    main()
