# Energy-Smells Taxonomy and Classification

This repository contains the dataset, methodology, and pipeline used for our research to define a comprehensive, language-agnostic taxonomy of software energy smells. It tracks energy inefficiencies from the root cause (sub-category) to a broader energy smell (category) and validates this using execution energy profiling and LLM-based classification.

**Taxonomy reference:** The full taxonomy — all 12 categories and 65 subcategories with descriptions and examples — is documented in [taxonomy.md](taxonomy.md).

## Directory Structure

<pre>
Energy-Smells
├── <a href="codenet/">codenet/</a>                        # Test cases for Python programs
├── <a href="energy_smell_classifier/">energy_smell_classifier/</a>        # LLM classification pipeline
│   ├── <a href="energy_smell_classifier/classify_smells.py">classify_smells.py</a>          # Main script to classify energy smells via DeepSeek LLM
│   ├── <a href="energy_smell_classifier/organize_classified_smells.py">organize_classified_smells.py</a> # Script for post-processing classification output
│   ├── <a href="energy_smell_classifier/prompts.py">prompts.py</a>                  # Prompt templates for the 3-step LLM classification
│   ├── <a href="energy_smell_classifier/simulate_prompts.py">simulate_prompts.py</a>         # Utility to test and simulate prompt iterations
│   └── <a href="energy_smell_classifier/utils.py">utils.py</a>                    # Helper functions for the LLM pipeline
├── <a href="literature_review_results/">literature_review_results/</a>      # Stages of the systematic literature review
│   ├── <a href="literature_review_results/v1_literature_review_collection.xls">v1_literature_review_collection.xls</a>
│   ├── <a href="literature_review_results/v2_literature_review_filtering.xls">v2_literature_review_filtering.xls</a>
│   ├── <a href="literature_review_results/v3_literature_review_annotator1_relevant_check.xls">v3_literature_review_annotator1_relevant_check.xls</a>
│   ├── <a href="literature_review_results/v3_literature_review_annotator2_relevant_check.xls">v3_literature_review_annotator2_relevant_check.xls</a>
│   ├── <a href="literature_review_results/v4_discussion_literature_review.xlsx">v4_discussion_literature_review.xlsx</a>
│   ├── <a href="literature_review_results/v5_relevant_kept_only_concatenated.xlsx">v5_relevant_kept_only_concatenated.xlsx</a>
│   ├── <a href="literature_review_results/v6_annotator1_opencoding.xlsx">v6_annotator1_opencoding.xlsx</a>
│   ├── <a href="literature_review_results/v6_annotator2_opencoding.xlsx">v6_annotator2_opencoding.xlsx</a>
│   ├── <a href="literature_review_results/v7_energy_smells_taxonomy.xlsx">v7_energy_smells_taxonomy.xlsx</a>
│   └── <a href="literature_review_results/v7_energy_smells_taxonomy_python_desc.xlsx">v7_energy_smells_taxonomy_python_desc.xlsx</a>
├── <a href="energy_results.jsonl">energy_results.jsonl</a>            # Intermediate dataset with energy measurements
├── <a href="taxonomy.md">taxonomy.md</a>                     # Full taxonomy: all 12 categories and 65 subcategories with descriptions
├── <a href="energy_smells_taxonomy.xlsx">energy_smells_taxonomy.xlsx</a>     # Final defined taxonomy
├── <a href="filter_significant_energy.py">filter_significant_energy.py</a>    # Script to isolate pairs with high energy divergence
├── <a href="measure_energy.py">measure_energy.py</a>               # Script to run perf tools and record energy/memory/time
├── <a href="requirements.txt">requirements.txt</a>                # Python dependencies
├── <a href="significant_energy_diff.jsonl">significant_energy_diff.jsonl</a>   # Filtered dataset containing significant top pairs
├── <a href="test_runner.py">test_runner.py</a>                  # Wrapper script to execute tests iteratively
├── <a href="train.jsonl">train.jsonl</a>                     # Input list of problem pairs from Pie-Perf dataset
├── <a href="validate_correctness.py">validate_correctness.py</a>         # Script to ensure functional equivalence of code pairs
├── <a href="validated_train.jsonl">validated_train.jsonl</a>           # Validation outputs
├── <a href="warmup.py">warmup.py</a>                       # Helper script to busy-wait the CPU before profiling
└── <a href="analysis/">analysis/</a>                       # Replication package: analysis script + dataset + generated results
    ├── <a href="analysis/analysis.py">analysis.py</a>                 # Full quantitative analysis and plot generation
    ├── <a href="analysis/classified_smells_final.jsonl">classified_smells_final.jsonl</a> # Final classified dataset (3,000 pairs)
    └── <a href="analysis/result/">result/</a>                     # Auto-generated: plots (.png/.pdf) + analysis_results.txt
</pre>

## Methodology Overview

The primary objective of this project is to categorize inefficiencies into a two-level hierarchy mapping:
1. **Energy Smell (Category)**: High-level observable patterns of resource waste that occur without altering the program's correctness.
2. **Root Cause (Sub-category)**: The specific technical misstep triggering the waste.

### Systematic Literature Review
The `literature_review_results/` folder captures the rigorous 5-phase systematic mapping study used to extract and classify patterns:
- **Phase 1 & 2 (`v1`, `v2`)**: Primary text query on Scopus and recursive snowballing of 400+ papers, resulting in an initial extraction of performance/energy anti-patterns.
- **Phase 3 (`v3_1`, `v3_2`, `v4`, `v5`)**: Dual-annotator assessment using inclusion/exclusion criteria to verify cross-language generalizability and relevance to Python.
- **Phase 4 (`v6_1`, `v6_2`)**: Qualitative coding to distill 320 remaining patterns down to their fundamental root causes via open and axial coding.
- **Phase 5 (`v7`)**: Taxonomy conflict resolution. The final result is a taxonomy comprising 12 top-level Energy Smells and 65 underlying Root Causes.

## Pipeline Usage & Replication

Follow these steps sequentially to replicate the dataset validation, measurement, and classification mechanisms:

### 0. Setup Virtual Environment
It is highly recommended to use a virtual environment to manage dependencies:
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 1. Validate Correctness
Evaluate the dataset pairs (efficient vs. inefficient Python versions) using predefined tests from `train.jsonl` to ensure identical behavior.
```bash
python validate_correctness.py
```
**What this does**: It reads code snippets from the dataset, runs 5 random tests per problem natively using Python `subprocess`, and verifies both snippets return identically correct outputs. Non-matching pairs or timeouts are discarded. Outputs are saved to `validated_train.jsonl`.

### 2. Measure Energy Consumption
Profile the validated code snippets to gather actual energy usage metrics.
```bash
python measure_energy.py
```
**What this does**: Reads the functionally validated pairs. For each program, it performs a CPU warm-up (using `warmup.py`), and executes the snippets iteratively (via `test_runner.py`) wrapping them within the Linux `perf stat` (extracting `energy-pkg` and `energy-ram` Joules) and `/usr/bin/time -v` (extracting Maximum Resident Set Size). Results are appended to `energy_results.jsonl`. 

*(Note: Depending on your system configuration, utilizing `perf stat` for hardware energy events might require administrative privileges or kernel parameter adjustments).*

**Dataset Fields Added**:
- `result_energy_v0` / `result_energy_v1`: Total Energy Joules.
- `result_time_v0` / `result_time_v1`: Elapsed time in seconds.
- `result_memory_v0` / `result_memory_v1`: Peak Memory (RSS) in KB.

### 3. Filter Significant Energy Differences
Locate instances that yield a high gap between efficient and inefficient code performance to ensure meaningful LLM classification.
```bash
python filter_significant_energy.py
```
**What this does**: Reads `energy_results.jsonl` into a Pandas DataFrame, calculates the absolute energy difference ($\Delta Energy$), and retains the top 3,000 thresholded pairs. This process guarantees extreme deviations are highlighted, writing the trimmed rows into `significant_energy_diff.jsonl`.

**Dataset Fields Added**: 
- `unique_index`: A persistent ID mapping back to the row index of `energy_results.jsonl`.

### 4. Classify Energy Smells via LLM
Execute the multi-step DeepSeek pipeline to label the fundamental root causes of the 3,000 selected instances.
```bash
# Ensure API_KEY and other parameters are supplied via .env
cd energy_smell_classifier
python classify_smells.py
```
**What this does**: Parses `significant_energy_diff.jsonl` and performs a sequential three-prompt analysis per instance using a highly threaded executor:
1. **Root Cause Analysis**: Extracts the technical reason the inefficiency exists, combining problem descriptions, code diffs, energy, time, and memory metrics.
2. **Category Triage**: Maps the determined root cause to the most applicable of the 12 primary Energy Smell labels.
3. **Subcategory Classification**: Identifies the most precise Subcategory tags within the selected parent smell.

Classification responses and AI rationale strings stream directly into `.jsonl` outputs located in the `energy_smell_classifier` folder.

**Dataset Fields Added**:
- `energy_diff`: The absolute energy difference between efficient and inefficient code.
- `llm_step1_root_cause`, `llm_step2_candidates`, `llm_step3_final`: Raw structured JSON output from the model.
- `llm_step1_reasoning`, `llm_step2_reasoning`, `llm_step3_reasoning`: The DeepSeek Chain-of-Thought (CoT) reasoning traces.
- `final_classification`: The conclusive list of predicted Root Cause subcategories (e.g., `["C1.S2", "C3.S1"]`).
- You can inspect the details of expected fields generated by LLMs in `energy_smell_classifier/prompts.py`.

### 5. Run Analysis & Generate Plots
Reproduce all quantitative findings and figures from the manuscript.
```bash
cd analysis
python analysis.py
```
**What this does**: Loads `classified_smells_final.jsonl`, computes all statistics reported in the manuscript, and saves results to `result/analysis_results.txt` along with publication-ready plots (PNG + PDF) in `result/`.

## Dataset Availability

The public version of our dataset, containing our newly appended fields, is available for download here: [**[Temporary Dataset Link (TODO)]**](#)

The dataset is provided in three ascending tiers of refinement:
1. `public_validated_energy_results.jsonl`: Contains all **21,428** problem pairs that successfully passed our functional equivalence test and were successfully profiled for energy, time, and memory consumption.
2. `public_significant_energy_diff.jsonl`: A filtered subset containing the top **3,000** pairs from the previous step that exhibited the highest absolute difference in energy consumption.
3. `public_classified_smells.jsonl`: The final **3,000** pairs from the significant difference tier, fully annotated with multi-step DeepSeek LLM reasoning, root causes, and final taxonomy subcategory classifications.
- Note: Any field except `user_id`, `problem_id`, `language`, `submission_id_v0`, `submission_id_v1`, `code_v0_no_empty_lines`, `code_v1_no_empty_lines` is generated by our pipeline.
## Credits
Our dataset extends the [Pie-Perf dataset](https://github.com/madaan/pie-perf?tab=readme-ov-file)---the python split [`train.jsonl`](https://drive.google.com/file/d/1ec8eOWgnBrzy2HlNDlTX6iURwQcIxDXH/view), which provides a rich collection of paired efficient and inefficient algorithmic implementations. While we retained their original paired snippet representations and problem descriptions, we expanded upon the dataset by profiling execution on hardware to measure and append our newly extracted `energy`, `time`, and `memory` metrics, alongside rigorous LLM-generated taxonomy classifications.