import json
import os
import random
import subprocess
import glob
import sys
import shutil
import re

# Configuration
DATASET_PATH = "validated_train.jsonl"
TEST_CASES_DIR = "codenet/generated_test_cases"
NUM_TEST_CASES = 50
OUTPUT_JSONL = "energy_results.jsonl"
TEMP_V0 = "temp_v0.py"
TEMP_V1 = "temp_v1.py"
TEST_RUNNER = "test_runner.py"
WARMUP_SCRIPT = "warmup.py"


def run_warmup():
    """Runs the warmup script."""
    try:
        subprocess.run(
            [sys.executable, WARMUP_SCRIPT],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"Warmup failed: {e}")


def run_perf_and_time(script_path, input_files):
    """
    Runs execution wrapped with perf and /usr/bin/time.
    Returns: energy (J), time (s), memory (KB).
    """
    if not input_files:
        return None, None, None

    # NO -x flag for perf, human readable output as requested.
    # perf stat -e energy-pkg,energy-ram /usr/bin/time -v python ...
    cmd = [
        "perf",
        "stat",
        "-e",
        "energy-pkg,energy-ram",
        "/usr/bin/time",
        "-v",
        sys.executable,
        TEST_RUNNER,
        script_path,
    ] + input_files

    try:
        # Capture stderr (where perf and time output goes)

        result = subprocess.run(cmd, capture_output=True, text=True)
        stderr_output = result.stderr

        energy_pkg = 0.0
        energy_ram = 0.0
        elapsed_time = 0.0
        max_rss = 0.0

        for line in stderr_output.splitlines():
            line = line.strip()

            # --- PARSE PERF (Human Readable) ---
            # Output format:
            # 1,198.06 Joules energy-pkg
            #   150.75 Joules energy-ram
            # 15.491325945 seconds time elapsed

            if "Joules energy-pkg" in line:
                try:
                    # Remove commas
                    clean_line = line.replace(",", "")
                    parts = clean_line.split()
                    # parts[0] is the number
                    energy_pkg = float(parts[0])
                except ValueError:
                    pass

            if "Joules energy-ram" in line:
                try:
                    clean_line = line.replace(",", "")
                    parts = clean_line.split()
                    energy_ram = float(parts[0])
                except ValueError:
                    pass

            if "seconds time elapsed" in line:
                try:
                    clean_line = line.replace(",", "")
                    # "15.491325945 seconds time elapsed"
                    parts = clean_line.split()
                    elapsed_time = float(parts[0])
                except ValueError:
                    pass

            # --- PARSE TIME (-v) ---
            # "Maximum resident set size (kbytes): 8480"
            if "Maximum resident set size (kbytes):" in line:
                try:
                    max_rss = float(line.split(":")[-1].strip())
                except ValueError:
                    pass

        total_energy = energy_pkg + energy_ram
        return total_energy, elapsed_time, max_rss

    except Exception as e:
        print(f"Error running execution: {e}")
        return None, None, None


def get_processed_count():
    if not os.path.exists(OUTPUT_JSONL):
        return 0
    with open(OUTPUT_JSONL, "r") as f:
        return sum(1 for _ in f)


def main():
    print(f"Reading {DATASET_PATH}...")
    if not os.path.exists(DATASET_PATH):
        print(f"Error: {DATASET_PATH} not found.")
        return

    with open(DATASET_PATH, "r") as f:
        all_samples = [json.loads(line) for line in f]

    processed_count = get_processed_count()
    print(
        f"Found {len(all_samples)} total samples. Already processed: {processed_count}"
    )

    samples_to_process = all_samples[processed_count:]

    with open(OUTPUT_JSONL, "a") as f_out:
        for i, data in enumerate(samples_to_process):
            current_idx = processed_count + i
            problem_id = data.get("problem_id")

            if not problem_id:
                continue

            code_v0 = data.get("code_v0_no_empty_lines")
            code_v1 = data.get("code_v1_no_empty_lines")

            if not code_v0 or not code_v1:
                print(f"Skipping {problem_id} (row {current_idx}): Missing code")
                data["error"] = "Missing code"
                f_out.write(json.dumps(data) + "\n")
                f_out.flush()
                continue

            # Write temp
            with open(TEMP_V0, "w") as f0:
                f0.write(code_v0)
            with open(TEMP_V1, "w") as f1:
                f1.write(code_v1)

            test_case_pattern = os.path.join(TEST_CASES_DIR, problem_id, "input.*.txt")
            input_files = glob.glob(test_case_pattern)

            if not input_files:
                print(f"Skipping {problem_id} (row {current_idx}): No test cases")
                data["error"] = "No test cases"
                f_out.write(json.dumps(data) + "\n")
                f_out.flush()
                continue

            selected_inputs = random.sample(
                input_files, min(len(input_files), NUM_TEST_CASES)
            )

            print(
                f"Processing row {current_idx}: {problem_id} with {len(selected_inputs)} inputs"
            )

            # WARMUP
            run_warmup()

            # MEASURE V0
            en_v0, t_v0, m_v0 = run_perf_and_time(TEMP_V0, selected_inputs)

            # WARMUP
            run_warmup()

            # MEASURE V1
            en_v1, t_v1, m_v1 = run_perf_and_time(TEMP_V1, selected_inputs)

            if en_v0 is not None and en_v1 is not None:
                data["result_energy_v0"] = en_v0
                data["result_time_v0"] = t_v0
                data["result_memory_v0"] = m_v0

                data["result_energy_v1"] = en_v1
                data["result_time_v1"] = t_v1
                data["result_memory_v1"] = m_v1

                f_out.write(json.dumps(data) + "\n")
                f_out.flush()
            else:
                print(f"Measurement failed for {problem_id}")
                data["error"] = "Measurement failed"
                f_out.write(json.dumps(data) + "\n")
                f_out.flush()

    print("Processing complete.")


if __name__ == "__main__":
    main()
