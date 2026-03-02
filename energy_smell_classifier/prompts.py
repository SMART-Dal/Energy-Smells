PROMPT_STEP_1 = """You are an expert in Python energy inefficiency analysis. Energy inefficiency can be correlated to performance inefficiency (time and memory) sometimes.

Goal:
Extract the TRUE root cause(s) of inefficiency (energy/performance) between two functionally equivalent solutions. You will be given the energy consumption, execution time, and memory usage of both codes. So based on the energy consumption variance and the auxiliary metrics of time and memory, identify the root cause(s) of energy inefficiency for both codes.
BOTH codes produce the same outputs for all valid inputs.

IMPORTANT RULES:
- Use the problem description to infer constraints and intended behavior.
- Identify what *changed* and which change(s) plausibly explain the measured metric lifts.
- Analyze the code changes very carefully and think deeply about what caused the inefficiency in chain of thought mode.
- So based on the changes and your programming knowledge, determine the root cause of inefficiency, i.e., the set of changes that lead to the inefficiency. 
- DO NOT reveal chain-of-thought or step-by-step reasoning in the output.
- Output MUST be a single valid JSON object (no markdown, no extra text).

Calibration example (for style + depth, not for labeling):
Inefficient:
numbers = [1,2,3,4,5]
squared = [x*x for x in numbers]
total = sum(squared)

Efficient:
numbers = [1,2,3,4,5]
total = sum(x*x for x in numbers)

Expected analysis idea:
The inefficient code materializes an intermediate list (squared), increasing allocations and memory pressure.
The efficient code uses a generator expression, computing items lazily and avoiding the temporary list.
This reduces memory usage and often reduces energy/time due to fewer allocations.

Now analyze THIS pair of efficient and inefficient codes. The inefficient code always indicates higher energy consumption, however the reported metrics of time and memory can either be higher or lower from the efficient code. Those metrics are auxiliary to help you find the root causes of energy inefficiency.

Problem Description (may be truncated):
{problem_description}

Code A (Inefficient):
- energy_joules: {energy_ineff}
- time_seconds: {time_ineff}
- memory_kb: {mem_ineff}
```python
{code_ineff}
```

Code B (Efficient):
- energy_joules: {energy_eff}
- time_seconds: {time_eff}
- memory_kb: {mem_eff}
```python
{code_eff}
```

Return ONLY this JSON schema:
{{
  "inefficiency_summary": "3-5 sentences. Describe the root cause clearly. Analyze the code changes. Does the saving come from reduced complexity, memory allocation, localized optimizations, etc.?",
}}
"""

PROMPT_STEP_2 = """You are Step 2 (Triage): choose the best matching PARENT energy-smell categories.

Context:
- You already saw the problem description and both code versions above.
- You already produced Step 1 JSON right above this message. Here is the output of Step 1 regarding the root cause of inefficiency:
{step1_output}

RULES:
- Focus on the ROOT CAUSE(S), not downstream effects.
- You may select MULTIPLE categories.
- You MUST return at least 1 category.
- Think internally very clearly and very carefully and see the definition of each category very carefully and see which ones match and are similar to the root cause the most.
- DO NOT reveal chain-of-thought.
- Output MUST be strict JSON only.

Parent Categories (C1-C12):
{categories_list}

Return ONLY this JSON:
{{
  "candidate_categories": ["C#"...],
  "category_rationales": {{
    "C#": "2-4 sentences explaining why this category matches the ROOT CAUSE clearly, referencing evidence."
  }}
}}
Constraints:
- candidate_categories must be unique.
- categories identified can be as many as you think matches best to the problem.
"""

PROMPT_STEP_3 = """You are Step 3 (Specialist): select final subcategory labels under the likely parent categories.

Context:
- You already saw the problem and both code versions above.
- You already produced Step 1 JSON and Step 2 JSON above this message.

RULES (follow strictly):
- Each sample MUST have at least ONE (category_id, subcategory_id) pair in the final output.
- Focus on Root Causes: Do NOT label downstream effects. If one code smell causes another symptom, label ONLY the root smell.
- Step-by-Step Evaluation: For EACH candidate subcategory, explicitly compare its definition and example with the specific code changes and the root cause of the inefficiency and select that subcategory if there is a clear, well-justified match.
- Strict Parent Discarding: If a parent category was suggested earlier but NONE of its provided subcategories fit the evaluation above, DISCARD that parent entirely.
- Strict Independence Constraint: You may output multiple subcategories (even under the same parent) IF AND ONLY IF they represent truly independent root causes. 

- Analyze the subcategories very carefully and think deeply about what subcategories fits to current inefficiency the most in the chain of thought mode.
- Think internally; DO NOT reveal chain-of-thought.
- Output MUST be strict JSON only.

Candidate parents from Step 2:
{selected_parents}

Available Subcategories (ONLY for candidate parents):
{subcategories_list}

Return ONLY this JSON schema:
{{
  "final_classification": [
    {{
      "category_id": "C#",
      "subcategory_id": "C#.S#",
      "justification": "2-4 sentences. Explain why you think this subcategory fits to current inefficiency."
    }},
    ...
  ]
}}
Constraints:
- final_classification must have length >= 1.
"""
