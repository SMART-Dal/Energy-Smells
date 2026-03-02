import json
import os
import random
import glob
import sys
import subprocess
import tempfile

def validate_code(code_str, input_file_path, expected_output_str, tmp_dir):
    # Write code to a temporary file
    with tempfile.NamedTemporaryFile(mode="w", dir=tmp_dir, suffix=".py", delete=False) as temp_code:
        temp_code.write(code_str)
        temp_code_path = temp_code.name

    try:
        with open(input_file_path, "r") as f_in:
            result = subprocess.run(
                [sys.executable, temp_code_path],
                stdin=f_in,
                capture_output=True,
                text=True,
                timeout=4.0
            )

        if result.returncode != 0:
            return False, f"Execution error: {result.stderr.strip()}"

        actual_output = result.stdout.strip()
        expected_output = expected_output_str.strip()

        if actual_output == expected_output:
            return True, ""
        else:
            return False, f"Output mismatch"

    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, f"Exception: {e}"
    finally:
        if os.path.exists(temp_code_path):
            os.remove(temp_code_path)


def main():
    input_jsonl = "train.jsonl"
    output_jsonl = "validated_train.jsonl"
    test_cases_dir = "codenet/generated_test_cases"
    tmp_dir = "tmp_run"
    
    # Create the temporary run directory if it doesn't exist
    os.makedirs(tmp_dir, exist_ok=True)
    
    # Read indices to test optionally
    indices_to_test = None
    if len(sys.argv) > 1:
        indices_to_test = [int(x) for x in sys.argv[1:]]

    if not os.path.exists(input_jsonl):
        print(f"Error: {input_jsonl} not found.")
        return

    print(f"Validating correctness from {input_jsonl} to {output_jsonl}...")

    invalid_count = 0
    valid_count = 0

    with open(input_jsonl, "r") as f_in, open(output_jsonl, "w") as f_out:
        for i, line in enumerate(f_in):
            if indices_to_test is not None and i not in indices_to_test:
                continue

            data = json.loads(line)
            problem_id = data.get("problem_id")
            
            # Print current row for tracking, especially during testing specific index
            if indices_to_test is not None:
                print(f"\nEvaluating row {i} (problem: {problem_id})")

            code_v0 = data.get("code_v0_no_empty_lines")
            code_v1 = data.get("code_v1_no_empty_lines")

            if not code_v0 or not code_v1 or not problem_id:
                invalid_count += 1
                print("Missing code or problem_id.")
                continue

            test_case_pattern = os.path.join(test_cases_dir, problem_id, "input.*.txt")
            input_files = glob.glob(test_case_pattern)

            if not input_files:
                invalid_count += 1
                print("No test cases found.")
                continue

            # Take 5 random test cases
            num_to_test = min(len(input_files), 5)
            selected_inputs = random.sample(input_files, num_to_test)
            
            is_valid = True
            for input_file in selected_inputs:
                # Find matching output file
                output_file = input_file.replace("input.", "output.")
                if not os.path.exists(output_file):
                    is_valid = False
                    print(f"Missing output file: {output_file}")
                    break
                
                with open(output_file, "r") as f:
                    expected_output = f.read()
                
                # Check v0
                v0_pass, v0_err = validate_code(code_v0, input_file, expected_output, tmp_dir)
                if not v0_pass:
                    is_valid = False
                    print(f"v0 failed on {os.path.basename(input_file)}: {v0_err}")
                    break
                
                # Check v1
                v1_pass, v1_err = validate_code(code_v1, input_file, expected_output, tmp_dir)
                if not v1_pass:
                    is_valid = False
                    print(f"v1 failed on {os.path.basename(input_file)}: {v1_err}")
                    break

            if is_valid:
                valid_count += 1
                f_out.write(json.dumps(data) + "\n")
                print("Pass: Both versions match expected output!")
            else:
                invalid_count += 1
            print("-" * 10)
            print(f"{i+1} done")
            print("-" * 100)
    print(f"\nDone! Valid samples: {valid_count}, Invalid/Skipped samples: {invalid_count}")
    print(f"Validated dataset saved to {output_jsonl}")

if __name__ == "__main__":
    main()
