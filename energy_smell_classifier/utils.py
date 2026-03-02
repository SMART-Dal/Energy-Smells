import os
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# -----------------------
# Configuration
# -----------------------

SCRIPT_DIR = Path(__file__).resolve().parent

TAXONOMY_FILE = (SCRIPT_DIR / "../energy_smell_taxonomy.xlsx").resolve()
DATASET_FILE = (SCRIPT_DIR / "../significant_energy_diff.jsonl").resolve()
PROBLEM_DESC_DIR = (SCRIPT_DIR / "../problem_descriptions").resolve()
OUTPUT_FILE = (SCRIPT_DIR / "classified_smells.jsonl").resolve()

BASE_URL = "https://openrouter.ai/api/v1"
API_KEY = os.getenv("OPENROUTER_API_KEY")

# Truncate problem description to avoid blowing context
DESC_MAX_CHARS = 4000

# LLM Constants
MODEL = "deepseek/deepseek-v3.2"
TEMPERATURE = 0
REASONING_MAX_TOKENS = 4096
MAX_JSON_PARSE_RETRIES = 2

# Runtime Constants
LIMIT: Optional[int] = None
RANDOM_SAMPLE_SIZE: Optional[int] = None
MAX_WORKERS = 25

# Rate Limiter
API_CALL_LOCK = threading.Lock()
LAST_API_CALL_TIME = 0.0
MIN_REQUEST_INTERVAL = 3  # Seconds between starting API calls


def rate_limit_wait():
    """
    Blocks thread execution to ensure a minimum time interval between API calls.
    Uses a global lock to manage the last call time safely across threads.
    """
    global LAST_API_CALL_TIME
    with API_CALL_LOCK:
        current_time = time.time()
        elapsed = current_time - LAST_API_CALL_TIME
        if elapsed < MIN_REQUEST_INTERVAL:
            sleep_time = MIN_REQUEST_INTERVAL - elapsed
            time.sleep(sleep_time)
        LAST_API_CALL_TIME = time.time()


def truncate_text(s: str, max_chars: int = DESC_MAX_CHARS) -> str:
    """
    Truncates the input string to the specified maximum number of characters.
    Also collapses multiple whitespace characters into a single space.
    """
    s = s or ""
    s = " ".join(s.split())
    return s[:max_chars]


def safe_float(x: Any, default: float = 0.0) -> float:
    """
    Safely converts a value to a float.
    Returns the default value if conversion fails or input is None.
    """
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def load_processed_ids() -> set:
    """Read OUTPUT_FILE to gather unique_indexes that have already been processed."""
    processed = set()
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "unique_index" in data:
                        processed.add(data["unique_index"])
                except json.JSONDecodeError:
                    continue
    return processed


def load_data() -> Tuple[pd.DataFrame, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Loads the taxonomy and dataset files, filters out already-processed items,
    and optionally takes a random sample.
    """
    logging.info(f"Loading taxonomy from: {TAXONOMY_FILE}")
    taxonomy_df = pd.read_excel(TAXONOMY_FILE)

    categories = taxonomy_df[taxonomy_df["Level"] == "Category"][
        ["ID", "Name", "Description"]
    ].to_dict("records")
    subcategories = taxonomy_df[taxonomy_df["Level"] == "Subcategory"][
        ["ID", "Name", "Parent_ID", "Description", "Example"]
    ].to_dict("records")

    logging.info(f"Loading dataset from: {DATASET_FILE}")
    rows: List[Dict[str, Any]] = []

    # Pre-load processed IDs to skip them quickly
    processed_ids = load_processed_ids()
    logging.info(f"Found {len(processed_ids)} already processed problems.")

    with open(DATASET_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            # Skip if already processed
            if data.get("unique_index") in processed_ids:
                continue
            rows.append(data)

    df = pd.DataFrame(rows)

    if df.empty:
        logging.info("No more unprocessed pairs left.")
        return df, categories, subcategories

    df["energy_diff_abs"] = (df["result_energy_v1"] - df["result_energy_v0"]).abs()

    # If random sampling is requested, sample here
    if RANDOM_SAMPLE_SIZE is not None and RANDOM_SAMPLE_SIZE > 0:
        n_sample = min(RANDOM_SAMPLE_SIZE, len(df))
        df = df.sample(n=n_sample, random_state=42)
    else:
        df = df.sort_values("energy_diff_abs", ascending=False)

    df = df.reset_index(drop=True)

    logging.info(f"Loaded {len(df)} pairs for this run.")
    return df, categories, subcategories


def get_problem_description(problem_id: Any) -> str:
    """
    Retrieves and cleans the problem description from the HTML file associated with the problem ID.

    Args:
        problem_id: The ID of the problem to fetch.

    Returns:
        str: The cleaned text content of the problem description.
    """
    if problem_id is None:
        return "Description not available."
    path = PROBLEM_DESC_DIR / f"{problem_id}.html"
    if not path.exists():
        return "Description not available."
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(content, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return truncate_text(text, DESC_MAX_CHARS)
    except Exception:
        return "Description not available."


def format_categories(categories: List[Dict[str, Any]]) -> str:
    """
    Formats the list of categories into a string for inclusion in the LLM prompt.
    """
    lines = []
    for c in categories:
        cid = str(c.get("ID", "")).strip()
        name = str(c.get("Name", "")).strip()
        desc = str(c.get("Description", "")).strip()
        lines.append(f"- {cid} — {name}: {desc}")
    return "\n".join(lines)


def format_subcategories(subs: List[Dict[str, Any]]) -> str:
    """
    Formats the list of subcategories into a string for inclusion in the LLM prompt.
    """
    lines = []
    for s in subs:
        sid = str(s.get("ID", "")).strip()
        name = str(s.get("Name", "")).strip()
        desc = str(s.get("Description", "")).strip()
        ex_val = s.get("Example", "")
        ex = (
            ""
            if (ex_val is None or (isinstance(ex_val, float) and pd.isna(ex_val)))
            else str(ex_val).strip()
        )
        if ex:
            lines.append(f"- {sid} — {name}: {desc} Example: {ex}")
        else:
            lines.append(f"- {sid} — {name}: {desc}")
    return "\n".join(lines)


def extract_json_fallback(text: str) -> Dict[str, Any]:
    """
    Robustly extracts a JSON object from a string.
    First tests direct parsing, then tries to find a JSON block if that fails.
    """
    text = (text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise


def pick_codes_and_metrics(
    row: pd.Series,
) -> Tuple[str, str, float, float, float, float, float, float]:
    """
    Determines which code version is efficient vs inefficient based on energy consumption.

    Args:
        row (pd.Series): A row from the dataset containing metrics and code.

    Returns:
        tuple: (code_eff, code_ineff, energy_eff, time_eff, mem_eff, energy_ineff, time_ineff, mem_ineff)
    """
    e0 = safe_float(row.get("result_energy_v0"))
    e1 = safe_float(row.get("result_energy_v1"))

    t0 = safe_float(row.get("result_time_v0"))
    t1 = safe_float(row.get("result_time_v1"))

    m0 = safe_float(row.get("result_memory_v0"), default=0.0)
    m1 = safe_float(row.get("result_memory_v1"), default=0.0)

    code0 = str(row.get("code_v0_no_empty_lines", "") or "")
    code1 = str(row.get("code_v1_no_empty_lines", "") or "")

    # Efficient = lower energy
    if e1 < e0:
        code_eff = code1
        code_ineff = code0
        energy_eff = e1
        time_eff = t1
        mem_eff = m1
        energy_ineff = e0
        time_ineff = t0
        mem_ineff = m0
    else:
        code_eff = code0
        code_ineff = code1
        energy_eff = e0
        time_eff = t0
        mem_eff = m0
        energy_ineff = e1
        time_ineff = t1
        mem_ineff = m1

    return (
        code_eff,
        code_ineff,
        energy_eff,
        time_eff,
        mem_eff,
        energy_ineff,
        time_ineff,
        mem_ineff,
    )


def call_llm(
    client: OpenAI,
    messages: List[Dict[str, str]],
    max_retries: int = MAX_JSON_PARSE_RETRIES,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    Calls the LLM API via OpenAI SDK using a message history.
    Handles rate limiting and retries for JSON parsing errors.

    Args:
        client: The OpenAI client instance.
        messages: List of message dictionaries.
        max_retries: Number of times to retry if JSON parsing fails.

    Returns:
        tuple: (json_obj, raw_content_str). Returns (None, None) on failure.
    """
    last_err: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            # Enforce rate limit before making request
            rate_limit_wait()

            resp = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=TEMPERATURE,
                extra_body={
                    "reasoning": {
                        "enabled": True,
                        "max_tokens": REASONING_MAX_TOKENS,
                    }
                },
            )
            content = (resp.choices[0].message.content or "").strip()
            reasoning = (resp.choices[0].message.reasoning or "").strip()
            # OpenRouter/DeepSeek sometimes wraps JSON in markdown blocks
            clean_content = content
            if clean_content.startswith("```json"):
                clean_content = clean_content[7:]
            if clean_content.endswith("```"):
                clean_content = clean_content[:-3]
            clean_content = clean_content.strip()

            return extract_json_fallback(clean_content), content, reasoning
        except Exception as e:
            last_err = e
            logging.warning(
                f"LLM call failed (attempt {attempt+1}/{max_retries+1}): {e}"
            )

    logging.error(f"LLM call ultimately failed: {last_err}")
    # User requested no special error handling for quota, just return None
    return None, None, None
