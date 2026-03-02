#!/usr/bin/env python3

import json
import logging
import threading
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Adjust path to ensure imports work
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.append(str(SCRIPT_DIR))

from tqdm import tqdm
from openai import OpenAI
import pandas as pd

from prompts import PROMPT_STEP_1, PROMPT_STEP_2, PROMPT_STEP_3
from utils import (
    API_KEY,
    BASE_URL,
    MAX_WORKERS,
    MODEL,
    OUTPUT_FILE,
    call_llm,
    format_categories,
    format_subcategories,
    get_problem_description,
    load_data,
    pick_codes_and_metrics,
)

# -----------------------
# Configuration
# -----------------------

# Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# -----------------------
# Processing Logic
# -----------------------

print("started .......")


def process_pair(
    pair_idx: int,
    row: pd.Series,
    client: OpenAI,
    cats_list_str: str,
    subcategories: list,
    output_lock: threading.Lock,
    out_f,
) -> bool:
    """
    Process a single pair. Returns True if successful, False otherwise.
    Writes result to out_f using output_lock.
    """
    try:
        (
            code_eff,
            code_ineff,
            energy_eff,
            time_eff,
            mem_eff,
            energy_ineff,
            time_ineff,
            mem_ineff,
        ) = pick_codes_and_metrics(row)

        # Problem description
        desc = get_problem_description(row.get("problem_id"))

        # Start message history
        messages = [
            {
                "role": "system",
                "content": "Return ONLY valid JSON. No markdown. No extra text.",
            }
        ]

        # ----- Step 1 -----
        prompt1 = PROMPT_STEP_1.format(
            energy_eff=energy_eff,
            time_eff=time_eff,
            mem_eff=mem_eff,
            energy_ineff=energy_ineff,
            time_ineff=time_ineff,
            mem_ineff=mem_ineff,
            problem_description=desc,
            code_ineff=code_ineff,
            code_eff=code_eff,
        )
        messages.append({"role": "user", "content": prompt1})

        res1, raw_content1, reasoning1 = call_llm(client, messages)
        # Check if call_llm returned None (failure)
        if res1 is None:
            logging.warning(f"Step 1 failed for pair {pair_idx}")
            return False

        # Append assistant response to history
        messages.append({"role": "assistant", "content": raw_content1})

        # ----- Step 2 -----
        prompt2 = PROMPT_STEP_2.format(
            step1_output=json.dumps(res1, ensure_ascii=False, indent=2),
            categories_list=cats_list_str,
        )
        messages.append({"role": "user", "content": prompt2})

        res2, raw_content2, reasoning2 = call_llm(client, messages)
        if res2 is None:
            logging.warning(f"Step 2 failed for pair {pair_idx}")
            return False

        # Append assistant response
        messages.append({"role": "assistant", "content": raw_content2})

        candidate_cats = res2.get("candidate_categories", []) or []
        if not candidate_cats:
            logging.warning(
                f"Step 2 returned empty categories for pair {pair_idx}; skipping."
            )
            return False

        # Filter relevant subcategories
        candidate_set = set(map(str, candidate_cats))
        relevant_subs = [
            s
            for s in subcategories
            if str(s.get("Parent_ID", "")).strip() in candidate_set
        ]
        subs_list_str = format_subcategories(relevant_subs)

        # ----- Step 3 -----
        prompt3 = PROMPT_STEP_3.format(
            selected_parents=json.dumps(candidate_cats, ensure_ascii=False),
            subcategories_list=subs_list_str,
        )
        messages.append({"role": "user", "content": prompt3})

        res3, raw_content3, reasoning3 = call_llm(client, messages)
        if res3 is None:
            logging.warning(f"Step 3 failed for pair {pair_idx}")
            return False

        final_class = res3.get("final_classification", []) or []
        if not final_class:
            logging.warning(
                f"Empty final classification for pair {pair_idx}; skipping."
            )
            return False

        # Build result object (preserve all original keys + add new ones)
        result_obj = row.to_dict()
        result_obj.update(
            {
                "llm_step1_root_cause": res1,
                "llm_step2_candidates": res2,
                "llm_step3_final": res3,
                "final_classification": final_class,
                "llm_step1_reasoning": reasoning1,
                "llm_step2_reasoning": reasoning2,
                "llm_step3_reasoning": reasoning3,
            }
        )

        with output_lock:
            # ensure_ascii=False to preserve unicode characters
            json.dump(result_obj, out_f, ensure_ascii=False)
            out_f.write("\n")
            out_f.flush()

        return True

    except Exception as e:
        logging.error(f"Error processing pair {pair_idx}: {e}")
        return False


# -----------------------
# Main
# -----------------------


def main() -> None:
    if not API_KEY:
        logging.error("OPENROUTER_API_KEY not found in environment variables.")
        return

    # OpenAI client is thread-safe
    client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

    try:
        df, categories, subcategories = load_data()
    except Exception as e:
        logging.error(f"Failed to load data/taxonomy: {e}")
        return

    # Ensure directories exist
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    cats_list_str = format_categories(categories)

    # Open output file in append mode.
    out_f = open(OUTPUT_FILE, "a", encoding="utf-8")
    output_lock = threading.Lock()

    if df.empty:
        logging.info("No data left to process. Exiting.")
        return

    n_total = len(df)
    logging.info(f"Starting classification for {n_total} item(s). Model={MODEL}")
    logging.info(f"Parallel execution with {MAX_WORKERS} workers.")

    # Prepare rows to process
    rows_to_process = []
    for pair_idx, row in df.iterrows():
        rows_to_process.append((pair_idx, row))

    processed_count = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for pair_idx, row in rows_to_process:
            f = executor.submit(
                process_pair,
                pair_idx,
                row,
                client,
                cats_list_str,
                subcategories,
                output_lock,
                out_f,
            )
            futures.append(f)

        # Wait for results and update progress bar
        try:
            for f in tqdm(as_completed(futures), total=len(futures)):
                try:
                    if f.result():
                        processed_count += 1
                except Exception as e:
                    logging.error(f"Worker exception: {e}")
        except KeyboardInterrupt:
            logging.info("Interrupted by user. Shutting down...")
            executor.shutdown(wait=False, cancel_futures=True)

    out_f.close()
    logging.info(
        f"Done. Processed {processed_count}/{len(futures)}. Output: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
