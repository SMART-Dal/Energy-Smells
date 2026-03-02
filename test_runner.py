import sys
import subprocess
import argparse

def main():
    parser = argparse.ArgumentParser(
        description="Run a python script against multiple input files."
    )
    parser.add_argument("script_path", help="Path to the python script to run")
    parser.add_argument(
        "input_files", nargs="+", help="List of input files to feed to the script"
    )
    args = parser.parse_args()

    for input_file in args.input_files:
        for _ in range(3):
            with open(input_file, "r") as f:
                try:
                    subprocess.run(
                        [sys.executable, args.script_path],
                        stdin=f,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=4.0,
                    )
                except subprocess.TimeoutExpired:
                    pass


if __name__ == "__main__":
    main()
