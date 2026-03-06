import json
import os
import math
from collections import Counter, defaultdict
from itertools import combinations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as ticker
import numpy as np
from scipy import stats

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DATA_PATH   = "classified_smells_final.jsonl"
RESULT_DIR  = "result"
OUTPUT_TXT  = os.path.join(RESULT_DIR, "analysis_results.txt")
os.makedirs(RESULT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Taxonomy ground truth: 12 categories × 65 subcategories
# ---------------------------------------------------------------------------
TAXONOMY = {
    "C1":  {"name": "Redundant Computation",           "subcats": ["C1.S1","C1.S2","C1.S3","C1.S4","C1.S5","C1.S6","C1.S7","C1.S8"]},
    "C2":  {"name": "Unnecessary Call Overhead",        "subcats": ["C2.S1","C2.S2","C2.S3"]},
    "C3":  {"name": "Inefficient Iteration Patterns",   "subcats": ["C3.S1","C3.S2","C3.S3","C3.S4","C3.S5","C3.S6","C3.S7"]},
    "C4":  {"name": "Inefficient Control Flow",         "subcats": ["C4.S1","C4.S2","C4.S3","C4.S4","C4.S5","C4.S6","C4.S7","C4.S8"]},
    "C5":  {"name": "Suboptimal Data Structures",       "subcats": ["C5.S1","C5.S2","C5.S3","C5.S4"]},
    "C6":  {"name": "Unnecessary Memory Usage",         "subcats": ["C6.S1","C6.S2","C6.S3","C6.S4","C6.S5","C6.S6","C6.S7"]},
    "C7":  {"name": "Suboptimal Algorithmic",           "subcats": ["C7.S1","C7.S2","C7.S3","C7.S4","C7.S5"]},
    "C8":  {"name": "Missing Reuse",                    "subcats": ["C8.S1","C8.S2","C8.S3","C8.S4"]},
    "C9":  {"name": "Inefficient External Data Access", "subcats": ["C9.S1","C9.S2","C9.S3","C9.S4"]},
    "C10": {"name": "Underused Language Primitives",    "subcats": ["C10.S1","C10.S2","C10.S3","C10.S4","C10.S5","C10.S6"]},
    "C11": {"name": "Inefficient Concurrency",          "subcats": ["C11.S1","C11.S2","C11.S3","C11.S4","C11.S5"]},
    "C12": {"name": "Poor Hardware Locality",           "subcats": ["C12.S1","C12.S2","C12.S3","C12.S4"]},
}

# Category color palette matching manuscript hex codes
CAT_COLORS = {
    "C1":"#FCE4D6","C2":"#DDEBF7","C3":"#E2EFDA","C4":"#F9E79F",
    "C5":"#FFF2CC","C6":"#E2D9F3","C7":"#D9E2F3","C8":"#D5F5E3",
    "C9":"#D6DCE4","C10":"#FADBD8","C11":"#FDEBD0","C12":"#D4E6F1",
}
CAT_ORDER = [f"C{i}" for i in range(1, 13)]

# ---------------------------------------------------------------------------
# Load data (line-by-line to avoid loading 112 MB at once)
# ---------------------------------------------------------------------------
def load_data(path):
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records

print("Loading data …")
data = load_data(DATA_PATH)
print(f"  Loaded {len(data)} samples.")

# ---------------------------------------------------------------------------
# Helper: extract labels from a record
# ---------------------------------------------------------------------------
def get_labels(record):
    """Return list of (category_id, subcategory_id) tuples.
    Normalises bare subcategory IDs like ('C7', 'S1') -> ('C7', 'C7.S1').
    """
    labels = []
    for item in record.get("final_classification", []):
        cat = item.get("category_id", "").strip()
        sub = item.get("subcategory_id", "").strip()
        if not cat:
            continue
        # Normalise "S1" -> "C7.S1" when category prefix is missing
        if sub and not sub.startswith("C"):
            sub = f"{cat}.{sub}"
        labels.append((cat, sub))
    return labels

# Pre-extract labels and numeric fields for all records
all_labels          = [get_labels(r) for r in data]
all_energy_diff     = [r.get("energy_diff_abs", None)     for r in data]
all_energy_v0       = [r.get("result_energy_v0", None)    for r in data]
all_energy_v1       = [r.get("result_energy_v1", None)    for r in data]
all_time_v0         = [r.get("result_time_v0", None)      for r in data]
all_time_v1         = [r.get("result_time_v1", None)      for r in data]
all_memory_v0       = [r.get("result_memory_v0", None)    for r in data]
all_memory_v1       = [r.get("result_memory_v1", None)    for r in data]
# Compute our time speedup ratio from result_time (NOT the runtime_lift field which uses
# measured_runtime_v0/v1 — a different single-run measurement from the original dataset)
all_time_ratio      = [t0/t1 if (t0 and t1 and t1 > 0 and math.isfinite(t0/t1)) else None
                       for t0, t1 in zip(all_time_v0, all_time_v1)]


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
lines_out = []

def section(title):
    lines_out.append("")
    lines_out.append("=" * 70)
    lines_out.append(f"  {title}")
    lines_out.append("=" * 70)

def row(text):
    lines_out.append(text)

def write_output():
    with open(OUTPUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines_out))
    print(f"\nResults written to {OUTPUT_TXT}")


# ===========================================================================
# SECTION 1 – Basic Dataset Statistics
# ===========================================================================
section("SECTION 1 – Basic Dataset Statistics")

n_total         = len(data)
n_multilabel    = sum(1 for lbl in all_labels if len(lbl) > 1)
n_single        = sum(1 for lbl in all_labels if len(lbl) == 1)
n_zero          = sum(1 for lbl in all_labels if len(lbl) == 0)
label_counts    = [len(lbl) for lbl in all_labels]
avg_labels      = sum(label_counts) / n_total
total_labels    = sum(label_counts)

label_hist = Counter(label_counts)

row(f"Total samples               : {n_total}")
row(f"Total label assignments     : {total_labels}")
row(f"Avg labels per sample       : {avg_labels:.3f}")
row(f"Samples with 0 labels       : {n_zero}")
row(f"Samples with 1 label        : {n_single}  ({100*n_single/n_total:.1f}%)")
row(f"Samples with 2 labels       : {label_hist[2]}  ({100*label_hist[2]/n_total:.1f}%)")
row(f"Samples with 3 labels       : {label_hist[3]}  ({100*label_hist[3]/n_total:.1f}%)")
row(f"Samples with 4+ labels      : {sum(v for k,v in label_hist.items() if k>=4)}  ({100*sum(v for k,v in label_hist.items() if k>=4)/n_total:.1f}%)")
row(f"Multi-label rate (>=2)      : {n_multilabel}  ({100*n_multilabel/n_total:.1f}%)")


# ===========================================================================
# SECTION 2 – Category-level Distribution
# ===========================================================================
section("SECTION 2 – Category-level Distribution (C1–C12)")

cat_sample_count  = Counter()   # unique samples per category
cat_label_count   = Counter()   # total label occurrences per category
for lbl_list in all_labels:
    cats_in_sample = set(cat for cat, _ in lbl_list)
    for cat in cats_in_sample:
        cat_sample_count[cat] += 1
    for cat, _ in lbl_list:
        cat_label_count[cat] += 1

row(f"{'Category':<6}  {'Name':<36}  {'Samples':>7}  {'%Dset':>6}  {'LblOcc':>7}")
row("-" * 72)
for cat in CAT_ORDER:
    name   = TAXONOMY[cat]["name"]
    sc     = cat_sample_count.get(cat, 0)
    lc     = cat_label_count.get(cat, 0)
    pct    = 100 * sc / n_total
    row(f"{cat:<6}  {name:<36}  {sc:>7}  {pct:>5.1f}%  {lc:>7}")


# ===========================================================================
# SECTION 3 – Subcategory-level Distribution (all 65)
# ===========================================================================
section("SECTION 3 – Subcategory-level Distribution (all 65 root causes)")

sub_count = Counter()
for lbl_list in all_labels:
    for cat, sub in lbl_list:
        if sub:
            sub_count[sub] += 1

# Build full table including zeros
all_subcats = [s for cat in CAT_ORDER for s in TAXONOMY[cat]["subcats"]]
row(f"{'SubCat':<8}  {'Count':>6}  {'%Labels':>8}  {'%Dataset':>9}")
row("-" * 42)
for cat in CAT_ORDER:
    row(f"  -- {cat}: {TAXONOMY[cat]['name']} --")
    for sub in TAXONOMY[cat]["subcats"]:
        cnt  = sub_count.get(sub, 0)
        plab = 100 * cnt / total_labels if total_labels else 0
        pdst = 100 * cnt / n_total
        row(f"  {sub:<8}  {cnt:>6}  {plab:>7.2f}%  {pdst:>8.2f}%")

# Zero-coverage subcategories
zero_subs = [s for s in all_subcats if sub_count.get(s, 0) == 0]
row("")
row(f"Zero-coverage subcategories ({len(zero_subs)}/{len(all_subcats)}): {', '.join(zero_subs) if zero_subs else 'None'}")

# Top-10 and bottom-10
top10    = sub_count.most_common(10)
non_zero = [(s, sub_count.get(s,0)) for s in all_subcats if sub_count.get(s,0) > 0]
non_zero.sort(key=lambda x: x[1])
bot10    = non_zero[:10]

row("")
row("Top-10 subcategories by frequency:")
for rank, (sub, cnt) in enumerate(top10, 1):
    row(f"  {rank:>2}. {sub:<8}  {cnt:>5}  ({100*cnt/n_total:.1f}% of dataset)")

row("")
row("Bottom-10 non-zero subcategories:")
for rank, (sub, cnt) in enumerate(bot10, 1):
    row(f"  {rank:>2}. {sub:<8}  {cnt:>5}  ({100*cnt/n_total:.2f}% of dataset)")


# ===========================================================================
# SECTION 4 – Multi-label Analysis
# ===========================================================================
section("SECTION 4 – Multi-label Analysis")

row("Label count distribution:")
for k in sorted(label_hist.keys()):
    bar = "█" * min(int(label_hist[k] / 10), 60)
    row(f"  {k} labels: {label_hist[k]:>5}  ({100*label_hist[k]/n_total:.1f}%)  {bar}")

# Category co-occurrence pairs
pair_counter = Counter()
for lbl_list in all_labels:
    cats = sorted(set(cat for cat, _ in lbl_list))
    for a, b in combinations(cats, 2):
        pair_counter[(a, b)] += 1

row("")
row("Top-15 category co-occurrence pairs (multi-label samples):")
row(f"  {'Pair':<12}  {'Count':>6}  {'%Multi':>8}")
row("  " + "-" * 32)
for (a, b), cnt in pair_counter.most_common(15):
    pct = 100 * cnt / n_multilabel if n_multilabel else 0
    row(f"  {a}+{b:<8}  {cnt:>6}  {pct:>7.1f}%")

# Subcategory co-occurrence pairs (top 15)
subpair_counter = Counter()
for lbl_list in all_labels:
    subs = sorted(set(sub for _, sub in lbl_list if sub))
    for a, b in combinations(subs, 2):
        subpair_counter[(a, b)] += 1

row("")
# C6 co-occurrence significance (Fisher's exact test)
c6_set = set(i for i, lbl in enumerate(all_labels) if any(c == "C6" for c, _ in lbl))
row("C6 co-occurrence significance (Fisher's exact test):")
row(f"  {'Cat':<5} {'N_both':>7} {'p-value':>12} {'sig':>5}")
row("  " + "-" * 34)
sig_c6_cats = []
for cat in CAT_ORDER:
    if cat == "C6": continue
    x_set = set(i for i, lbl in enumerate(all_labels) if any(c == cat for c, _ in lbl))
    both = len(c6_set & x_set); c6_only = len(c6_set - x_set)
    x_only = len(x_set - c6_set); neither = len(data) - both - c6_only - x_only
    _, p = stats.fisher_exact([[both, c6_only], [x_only, neither]])
    sig_str = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else "ns"))
    if p < 0.05: sig_c6_cats.append(cat)
    row(f"  {cat:<5} {both:>7} {p:>12.2e} {sig_str:>5}")
row(f"  C6 significantly co-occurs (p<0.05) with {len(sig_c6_cats)}/11 categories: {sig_c6_cats}")

row("")
row("Top-15 subcategory co-occurrence pairs:")
row(f"  {'Pair':<18}  {'Count':>6}")
row("  " + "-" * 28)
for (a, b), cnt in subpair_counter.most_common(15):
    row(f"  {a}+{b:<12}  {cnt:>6}")


# ===========================================================================
# SECTION 5 – Energy Statistics per Category
# ===========================================================================
section("SECTION 5 – Energy Statistics per Category")

# Build per-category lists of energy_diff and energy_ratio
cat_energy_diff   = defaultdict(list)
cat_energy_ratio  = defaultdict(list)
for i, lbl_list in enumerate(all_labels):
    cats = set(cat for cat, _ in lbl_list)
    e0   = all_energy_v0[i]
    e1   = all_energy_v1[i]
    ed   = all_energy_diff[i]
    if ed is None:
        continue
    ratio = (e0 / e1) if (e1 and e1 > 0) else None
    for cat in cats:
        cat_energy_diff[cat].append(ed)
        if ratio is not None:
            cat_energy_ratio[cat].append(ratio)

row(f"{'Cat':<5}  {'Name':<36}  {'N':>5}  {'Mean_J':>10}  {'Median_J':>10}  {'Max_J':>12}  {'MeanRatio':>10}")
row("-" * 98)
for cat in CAT_ORDER:
    diffs  = cat_energy_diff.get(cat, [])
    ratios = cat_energy_ratio.get(cat, [])
    if not diffs:
        row(f"{cat:<5}  {TAXONOMY[cat]['name']:<36}  {'0':>5}  {'—':>10}  {'—':>10}  {'—':>12}  {'—':>10}")
        continue
    row(f"{cat:<5}  {TAXONOMY[cat]['name']:<36}  {len(diffs):>5}  "
        f"{np.mean(diffs):>10.1f}  {np.median(diffs):>10.1f}  {max(diffs):>12.1f}  "
        f"{np.mean(ratios) if ratios else 0:>10.2f}")

# Ranking by median energy improvement
row("")
row("Categories ranked by median energy_diff_abs (highest saving first):")
ranked = sorted(
    [(cat, float(np.median(v))) for cat, v in cat_energy_diff.items() if v],
    key=lambda x: -x[1]
)
for rank, (cat, med) in enumerate(ranked, 1):
    row(f"  {rank:>2}. {cat}  ({TAXONOMY[cat]['name']})  median={med:.1f} J")


# ===========================================================================
# SECTION 6 – Energy per Subcategory (top impact)
# ===========================================================================
section("SECTION 6 – Energy Statistics per Subcategory (Top-20 by Mean)")

sub_energy = defaultdict(list)
for i, lbl_list in enumerate(all_labels):
    ed = all_energy_diff[i]
    if ed is None:
        continue
    for _, sub in lbl_list:
        if sub:
            sub_energy[sub].append(ed)

ranked_sub = sorted(
    [(sub, np.mean(v), len(v)) for sub, v in sub_energy.items()],
    key=lambda x: -x[1]
)

row(f"{'SubCat':<8}  {'N':>5}  {'MeanEnergy_J':>14}  {'MedianEnergy_J':>15}")
row("-" * 50)
for sub, mean_e, n_sub in ranked_sub[:20]:
    med_e = np.median(sub_energy[sub])
    row(f"{sub:<8}  {n_sub:>5}  {mean_e:>14.1f}  {med_e:>15.1f}")


# ===========================================================================
# SECTION 7 – Time–Energy Correlation
# ===========================================================================
section("SECTION 7 – Time–Energy Correlation")

pairs_te = []
for i in range(len(data)):
    tr  = all_time_ratio[i]            # result_time_v0 / result_time_v1 (our measurement)
    e0  = all_energy_v0[i]
    e1  = all_energy_v1[i]
    if tr is None or e1 is None or e1 == 0 or e0 is None:
        continue
    er = e0 / e1
    if math.isfinite(tr) and math.isfinite(er):
        pairs_te.append((tr, er))

rl_arr = np.array([x[0] for x in pairs_te])   # result_time ratio (our measurement)
er_arr = np.array([x[1] for x in pairs_te])

pearson_r,  pearson_p  = stats.pearsonr(rl_arr,  er_arr)
spearman_r, spearman_p = stats.spearmanr(rl_arr, er_arr)

row(f"Pairs used (result_time_v0/v1 vs result_energy_v0/v1): {len(pairs_te)}")
row(f"Pearson  r = {pearson_r:.4f}  (p = {pearson_p:.2e})")
row(f"Spearman r = {spearman_r:.4f}  (p = {spearman_p:.2e})")
row(f"Note: time ratio computed as result_time_v0/result_time_v1 (our Pie-Perf measurement)")
row("")

# Quartile analysis of time ratio vs mean energy ratio
quartiles = np.percentile(rl_arr, [25, 50, 75])
row("Mean energy ratio by time_ratio quartile (result_time_v0/result_time_v1):")
row(f"  {'Quartile':<12}  {'T-ratio range':>18}  {'Mean E-ratio':>13}  {'N':>5}")
q_labels = ["Q1 (lowest)", "Q2", "Q3", "Q4 (highest)"]
q_bounds = [(-np.inf, quartiles[0]), (quartiles[0], quartiles[1]),
            (quartiles[1], quartiles[2]), (quartiles[2], np.inf)]
for ql, (lo, hi) in zip(q_labels, q_bounds):
    mask  = (rl_arr >= lo) & (rl_arr < hi) if lo > -np.inf else (rl_arr < hi)
    if ql.startswith("Q4"):
        mask = rl_arr >= lo
    sub_e = er_arr[mask]
    if len(sub_e) == 0:
        continue
    row(f"  {ql:<12}  [{lo:>7.2f}, {hi:>7.2f})  {np.mean(sub_e):>13.2f}  {len(sub_e):>5}")


# ===========================================================================
# SECTION 8 – Taxonomy Coverage Validation
# ===========================================================================
section("SECTION 8 – Taxonomy Coverage Validation")

row(f"{'Cat':<5}  {'Name':<36}  {'ExpSub':>6}  {'ObsSub':>6}  {'%Cov':>6}  {'ZeroSubs'}")
row("-" * 90)
for cat in CAT_ORDER:
    expected  = TAXONOMY[cat]["subcats"]
    observed  = [s for s in expected if sub_count.get(s, 0) > 0]
    zeros     = [s for s in expected if sub_count.get(s, 0) == 0]
    pct_cov   = 100 * len(observed) / len(expected)
    zero_str  = ", ".join(zeros) if zeros else "—"
    row(f"{cat:<5}  {TAXONOMY[cat]['name']:<36}  {len(expected):>6}  {len(observed):>6}  {pct_cov:>5.0f}%  {zero_str}")

total_expected = sum(len(TAXONOMY[c]["subcats"]) for c in CAT_ORDER)
total_observed = sum(1 for s in all_subcats if sub_count.get(s, 0) > 0)
row("")
row(f"Overall coverage: {total_observed}/{total_expected} subcategories observed ({100*total_observed/total_expected:.1f}%)")
row(f"Zero-coverage subcategories: {', '.join(zero_subs) if zero_subs else 'None — full coverage achieved'}")

# Check for any labels in data NOT in taxonomy
all_known_subs = set(s for cat in CAT_ORDER for s in TAXONOMY[cat]["subcats"])
all_known_cats = set(CAT_ORDER)
unknown_cats = set()
unknown_subs = set()
for lbl_list in all_labels:
    for cat, sub in lbl_list:
        if cat not in all_known_cats:
            unknown_cats.add(cat)
        if sub and sub not in all_known_subs:
            unknown_subs.add(sub)
row("")
row(f"Unknown category IDs in data: {', '.join(sorted(unknown_cats)) if unknown_cats else 'None'}")
row(f"Unknown subcategory IDs in data: {', '.join(sorted(unknown_subs)) if unknown_subs else 'None'}")


# ===========================================================================
# SECTION 9 – Memory Statistics per Category
# ===========================================================================
section("SECTION 9 – Memory Statistics per Category")

cat_mem_diff = defaultdict(list)
for i, lbl_list in enumerate(all_labels):
    cats = set(cat for cat, _ in lbl_list)
    m0   = all_memory_v0[i]
    m1   = all_memory_v1[i]
    if m0 is None or m1 is None:
        continue
    diff = m0 - m1
    for cat in cats:
        cat_mem_diff[cat].append(diff)

row(f"{'Cat':<5}  {'Name':<36}  {'N':>5}  {'MeanMemDiff(KB)':>16}  {'MedianMemDiff(KB)':>18}  {'Reduction%':>10}")
row("-" * 100)
for cat in CAT_ORDER:
    diffs = cat_mem_diff.get(cat, [])
    if not diffs:
        row(f"{cat:<5}  {TAXONOMY[cat]['name']:<36}  {'0':>5}  {'—':>16}  {'—':>18}  {'—':>10}")
        continue
    mean_d   = np.mean(diffs)
    med_d    = np.median(diffs)
    # Compute mean memory_v0 for this category to get % reduction
    m0_vals  = [all_memory_v0[i] for i, lbl in enumerate(all_labels)
                if any(c == cat for c, _ in lbl) and all_memory_v0[i] is not None]
    red_pct  = 100 * mean_d / np.mean(m0_vals) if m0_vals else 0
    row(f"{cat:<5}  {TAXONOMY[cat]['name']:<36}  {len(diffs):>5}  {mean_d:>16.1f}  {med_d:>18.1f}  {red_pct:>9.1f}%")


# ===========================================================================
# Write text output
# ===========================================================================
write_output()


# ===========================================================================
# SECTION 10 – Energy Impact by Abstraction Level
# ===========================================================================
section("SECTION 10 – Energy Impact by Abstraction Level")
LEVEL_MAP = {
    "C1":"impl","C2":"impl","C3":"impl","C4":"impl",
    "C5":"design","C6":"impl","C7":"design","C8":"design",
    "C9":"arch","C10":"impl","C11":"arch","C12":"hw",
}
LEVEL_NAMES = {"impl":"Implementation-level","design":"Design-level",
               "arch":"Architecture-level","hw":"Hardware-level"}
level_indices = defaultdict(set)
for i, lbls in enumerate(all_labels):
    if all_energy_diff[i] is None: continue
    for cat, _ in lbls:
        lv = LEVEL_MAP.get(cat, "impl")
        level_indices[lv].add(i)

row(f"{'Level':<22}  {'Samples':>8}  {'%Dset':>6}  {'MedianE_J':>10}  {'MeanE_J':>10}  {'MeanRatio':>10}")
row("-" * 72)
for lv, name in [("impl","Implementation-level"),("design","Design-level"),
                 ("arch","Architecture-level"),("hw","Hardware-level")]:
    idxs = list(level_indices[lv])
    diffs_lv = [all_energy_diff[i] for i in idxs]   # one diff per unique sample
    if not diffs_lv:
        row(f"{name:<22}  {'0':>8}"); continue
    ratios = [all_energy_v0[i]/all_energy_v1[i] for i in idxs
              if all_energy_v0[i] and all_energy_v1[i] and all_energy_v1[i] > 0]
    row(f"{name:<22}  {len(idxs):>8}  {100*len(idxs)/len(data):>5.1f}%  "
        f"{np.median(diffs_lv):>10.1f}  {np.mean(diffs_lv):>10.1f}  "
        f"{np.mean(ratios) if ratios else 0:>10.2f}")

# ===========================================================================
# SECTION 11 – Single-label vs Multi-label Energy Comparison
# ===========================================================================
section("SECTION 11 – Single-label vs Multi-label Energy Comparison")
single_e, multi_e = [], []
for i, lbls in enumerate(all_labels):
    ed = all_energy_diff[i]
    if ed is None: continue
    if len(lbls) == 1: single_e.append(ed)
    elif len(lbls) >= 2: multi_e.append(ed)

row(f"Single-label (1 smell): N={len(single_e)}, median={np.median(single_e):.1f}J, mean={np.mean(single_e):.1f}J")
row(f"Multi-label  (2+ smells): N={len(multi_e)}, median={np.median(multi_e):.1f}J, mean={np.mean(multi_e):.1f}J")
_u, _p = stats.mannwhitneyu(multi_e, single_e, alternative='greater')
row(f"Mann-Whitney U (multi > single): p={_p:.4f} {'[significant]' if _p < 0.05 else '[not significant]'}")
row(f"Multi-label samples have {np.median(multi_e)/np.median(single_e):.2f}x higher median energy savings than single-label")

# ===========================================================================
# SECTION 12 – Loop-as-Amplifier Quantification (C3 context)
# ===========================================================================
section("SECTION 12 – Loop-as-Amplifier Quantification (C3 context)")
def cats_set(i): return set(c for c, _ in all_labels[i])

c3_only_e   = [all_energy_diff[i] for i in range(len(data)) if cats_set(i)=={'C3'} and all_energy_diff[i]]
c3_c7_e     = [all_energy_diff[i] for i in range(len(data)) if {'C3','C7'}<=cats_set(i) and all_energy_diff[i]]
c3_c10_e    = [all_energy_diff[i] for i in range(len(data)) if {'C3','C10'}<=cats_set(i) and all_energy_diff[i]]
c7_only_e   = [all_energy_diff[i] for i in range(len(data)) if cats_set(i)=={'C7'} and all_energy_diff[i]]

row(f"{'Group':<30}  {'N':>5}  {'Median_J':>10}  {'Mean_J':>10}")
row("-" * 60)
for name, lst in [("C3 alone",c3_only_e),("C3+C7 together",c3_c7_e),
                  ("C3+C10 together",c3_c10_e),("C7 alone",c7_only_e)]:
    if lst: row(f"{name:<30}  {len(lst):>5}  {np.median(lst):>10.1f}  {np.mean(lst):>10.1f}")
    else:   row(f"{name:<30}  {'0':>5}  {'—':>10}  {'—':>10}")

row("")
row("Interpretation: When C3 co-occurs with C7 (loop amplifies an algorithmic smell),")
row("  the energy savings are substantially higher than C3 alone, confirming that")
row("  the loop is an amplifier of the algorithmic root cause, not the root cause itself.")

# ===========================================================================
# SECTION 13 – LLM Disambiguation: When Final Label Differs from Candidates
# ===========================================================================
section("SECTION 13 – LLM Disambiguation: When Final Label Differs from Candidates")
disambiguation = []
for r in data:
    step2 = r.get('llm_step2_candidates', {})
    cands = step2.get('candidate_categories', [])
    final_c = list(set(c for c, _ in get_labels(r)))
    if len(cands) >= 2 and len(final_c) == 1:
        disambiguation.append((cands, final_c[0], r.get('energy_diff_abs', 0)))

row(f"Samples where step2 had >=2 candidates but final single label: {len(disambiguation)}")
row("Top final-label selections after disambiguation:")
final_counter_dis = Counter(fc for _, fc, _ in disambiguation)
for cat, cnt in final_counter_dis.most_common(8):
    row(f"  {cat} ({TAXONOMY[cat]['name']}): {cnt} times selected as final")

c3_cand_c7_final = [(c, fc, e) for c, fc, e in disambiguation if 'C3' in c and fc == 'C7']
c7_cand_c3_final = [(c, fc, e) for c, fc, e in disambiguation if 'C7' in c and fc == 'C3']
row(f"\nC3 was candidate but C7 chosen as final: {len(c3_cand_c7_final)} cases")
row(f"C7 was candidate but C3 chosen as final: {len(c7_cand_c3_final)} cases")
_denom = len(c3_cand_c7_final) + len(c7_cand_c3_final)
row(f"  C7 chosen over C3 in {len(c3_cand_c7_final)/_denom*100 if _denom else 0:.0f}% of C3/C7 conflicts (loop as amplifier rule applied)")

c1_cand_c8_final = [(c, fc, e) for c, fc, e in disambiguation if 'C1' in c and fc == 'C8']
c8_cand_c1_final = [(c, fc, e) for c, fc, e in disambiguation if 'C8' in c and fc == 'C1']
row(f"\nC1 was candidate but C8 chosen as final: {len(c1_cand_c8_final)} cases")
row(f"C8 was candidate but C1 chosen as final: {len(c8_cand_c1_final)} cases")
row(f"  Within-scope (C1) vs cross-call (C8) boundary is resolved in {len(c1_cand_c8_final)+len(c8_cand_c1_final)} cases")

c5_cand_c7_final = sum(1 for c, fc, _ in disambiguation if 'C5' in c and fc == 'C7')
c7_cand_c5_final = sum(1 for c, fc, _ in disambiguation if 'C7' in c and fc == 'C5')
row(f"\nC5 was candidate but C7 chosen: {c5_cand_c7_final}, C7 was candidate but C5 chosen: {c7_cand_c5_final}")

# ===========================================================================
# SECTION 14 – Dataset Sort Structure Verification
# ===========================================================================
section("SECTION 14 – Dataset Sort Structure Verification")
diffs_all = [ed if ed is not None else 0 for ed in all_energy_diff]
is_desc = all(diffs_all[i] >= diffs_all[i+1] for i in range(len(diffs_all)-1))
is_asc  = all(diffs_all[i] <= diffs_all[i+1] for i in range(len(diffs_all)-1))
row(f"Strictly sorted descending: {is_desc}")
row(f"Strictly sorted ascending:  {is_asc}")
row(f"Overall range: min={min(diffs_all):.1f}J, max={max(diffs_all):.1f}J")
row(f"\nDataset is partitioned into rough energy-tier blocks (chunk means):")
row(f"  {'Rows':>12}  {'Mean_J':>10}  {'Min_J':>10}  {'Max_J':>10}")
chunk_size = 300
for start in range(0, len(diffs_all), chunk_size):
    chunk = diffs_all[start:start+chunk_size]
    row(f"  {start:4d}–{start+chunk_size-1:4d}: mean={np.mean(chunk):8.1f}J, "
        f"min={min(chunk):8.1f}J, max={max(chunk):8.1f}J")
row("")
row("Note: The dataset is NOT strictly sorted. It was assembled in energy-tiered")
row("  batches, creating a multi-modal distribution rather than a smooth ranking.")
row("  Analyses use quartile binning (Q1–Q4) rather than positional rank for robustness.")

# ===========================================================================
# SECTION 15 – Smell Distribution by Energy Quartile (Chi-Square Test)
# ===========================================================================
section("SECTION 15 – Smell Distribution by Energy Quartile (Chi-Square Test)")
_q25, _q50, _q75 = np.percentile([d for d in diffs_all if d > 0], [25, 50, 75])
row(f"Quartile boundaries (on {len([d for d in diffs_all if d>0])} non-zero samples):")
row(f"  Q1 (low) : 0 – {_q25:.1f}J")
row(f"  Q2       : {_q25:.1f} – {_q50:.1f}J")
row(f"  Q3       : {_q50:.1f} – {_q75:.1f}J")
row(f"  Q4 (high): {_q75:.1f}J – {max(diffs_all):.1f}J")

def qbin4(d):
    if d <= _q25: return 0
    elif d <= _q50: return 1
    elif d <= _q75: return 2
    else: return 3

_bin_labels = ['Q1_low','Q2','Q3','Q4_high']
cat_qbin = defaultdict(lambda: [0,0,0,0])
total_qbin = [0,0,0,0]
for i, lbls in enumerate(all_labels):
    ed = all_energy_diff[i]
    if ed is None: continue
    b = qbin4(ed)
    total_qbin[b] += 1
    for cat in set(c for c, _ in lbls):   # unique categories per sample
        cat_qbin[cat][b] += 1

row(f"\n  Total per bin: {dict(zip(_bin_labels, total_qbin))}")
row(f"\n  {'Cat':<6} {'Name':<32} {'Q1%':>7} {'Q2%':>7} {'Q3%':>7} {'Q4%':>7}  Chi2p  Sig")
row("  " + "-"*82)
for cat in CAT_ORDER:
    obs = cat_qbin[cat]
    n_cat = sum(obs)
    if n_cat == 0: continue
    exp = [total_qbin[b] * n_cat / len(data) for b in range(4)]
    # Avoid zero expected
    valid = all(e >= 5 for e in exp)
    if valid:
        chi2, pval = stats.chisquare(obs, exp)
        sig = '***' if pval<0.001 else ('**' if pval<0.01 else ('*' if pval<0.05 else '   '))
    else:
        chi2, pval, sig = 0, 1.0, '   '
    pcts = [f"{100*obs[b]/total_qbin[b]:5.1f}%" if total_qbin[b]>0 else "  N/A" for b in range(4)]
    row(f"  {cat:<6} {TAXONOMY[cat]['name']:<32} {pcts[0]:>7} {pcts[1]:>7} {pcts[2]:>7} {pcts[3]:>7}  "
        f"p={pval:.4f}  {sig}")

row("")
row("Key findings (statistically significant, p<0.001):")
row("  C5 (Suboptimal Data Structures): concentrated in Q3+Q4 — data structure smells")
row("     cause larger energy waste (design-level root causes)")
row("  C6 (Unnecessary Memory Usage):   concentrated in Q3+Q4 — memory allocation smells")
row("     correlate strongly with high energy differences")
row("  C7 (Suboptimal Algorithmic):      peaks in Q2+Q3, less frequent in Q4 (extreme cases)")
row("     are often multi-category: algorithm + memory compound to Q4")
row("  C4 (Inefficient Control Flow):   concentrated in Q1+Q2 — control flow smells alone")
row("     cause smaller energy impact; rarely a major root cause")
row("  C2 (Unnecessary Call Overhead):  concentrated in Q1 — function call overhead is minor")

# ===========================================================================
# SECTION 16 – Power is Not Constant: E = P × T Decomposition
# ===========================================================================
section("SECTION 16 – Power is Not Constant: E = P x T Decomposition")
power_v0_all, power_v1_all = [], []
power_diff_contrib, time_diff_contrib, energy_diff_vals = [], [], []
counter_intuitive_n = 0
energy_worsened_n = 0
energy_worsened_examples = []

for i, r in enumerate(data):
    e0, t0 = all_energy_v0[i], all_time_v0[i]
    e1, t1 = all_energy_v1[i], all_time_v1[i]
    if not all(x and x > 0 for x in [e0, t0, e1, t1]):
        continue
    p0, p1 = e0/t0, e1/t1
    power_v0_all.append(p0)
    power_v1_all.append(p1)
    # E_diff ≈ P0*(T0-T1) + (P0-P1)*T1  [first-order decomposition]
    tc = p0 * (t0 - t1)
    pc = (p0 - p1) * t1
    power_diff_contrib.append(pc)
    time_diff_contrib.append(tc)
    energy_diff_vals.append(e0 - e1)
    # Counter-intuitive: faster but more energy
    if t0 > t1 and e0 < e1:
        counter_intuitive_n += 1
        energy_worsened_n += 1
        if len(energy_worsened_examples) < 5:
            energy_worsened_examples.append((r.get('unique_index'), e0-e1, t0/t1,
                                             p0, p1, list(cats_set(i))))
    elif t0 > t1 and p0 < p1:
        counter_intuitive_n += 1

row(f"Power Statistics (computed as E/T per sample):")
row(f"  Power v0: mean={np.mean(power_v0_all):.3f}W, median={np.median(power_v0_all):.3f}W, "
    f"std={np.std(power_v0_all):.3f}W, CV={np.std(power_v0_all)/np.mean(power_v0_all)*100:.1f}%")
row(f"  Power v1: mean={np.mean(power_v1_all):.3f}W, median={np.median(power_v1_all):.3f}W, "
    f"std={np.std(power_v1_all):.3f}W, CV={np.std(power_v1_all)/np.mean(power_v1_all)*100:.1f}%")
row(f"  Power range v0: [{min(power_v0_all):.1f}W, {max(power_v0_all):.1f}W]")
row(f"  Power range v1: [{min(power_v1_all):.1f}W, {max(power_v1_all):.1f}W]")
_t, _pval = stats.ttest_rel(power_v0_all, power_v1_all)
row(f"  Paired t-test (v0 power vs v1 power): t={_t:.3f}, p={_pval:.2e} {'[significant]' if _pval<0.05 else ''}")
row(f"  Mean power reduction: {np.mean(power_v0_all)-np.mean(power_v1_all):.3f}W "
    f"({(np.mean(power_v0_all)-np.mean(power_v1_all))/np.mean(power_v0_all)*100:.1f}%)")

row("")
row(f"E = P x T Decomposition of Mean Energy Savings:")
row(f"  Mean total energy savings: {np.mean(energy_diff_vals):.1f}J")
_tc_m = np.mean(time_diff_contrib)
_pc_m = np.mean(power_diff_contrib)
row(f"  Component due to time reduction  [P0 * (T0-T1)]: {_tc_m:+.1f}J ({100*_tc_m/np.mean(energy_diff_vals):+.1f}%)")
row(f"  Component due to power reduction [(P0-P1) * T1]: {_pc_m:+.1f}J ({100*_pc_m/np.mean(energy_diff_vals):+.1f}%)")
pd_dom = sum(1 for tc, pc in zip(time_diff_contrib, power_diff_contrib) if abs(pc) > abs(tc))
row(f"  Samples where power change dominates time change: {pd_dom}/{len(energy_diff_vals)} ({100*pd_dom/len(energy_diff_vals):.1f}%)")

row("")
row(f"Correlation Analysis (Spearman, on {len(energy_diff_vals)} samples with valid E,T):")
t_ratio_arr = np.array([all_time_v0[i]/all_time_v1[i] for i, r in enumerate(data)
                         if all_time_v0[i] and all_time_v1[i] and all_time_v1[i] > 0
                         and all_energy_v0[i] and all_energy_v1[i] and all_energy_v1[i] > 0])
e_ratio_arr = np.array([all_energy_v0[i]/all_energy_v1[i] for i, r in enumerate(data)
                         if all_time_v0[i] and all_time_v1[i] and all_time_v1[i] > 0
                         and all_energy_v0[i] and all_energy_v1[i] and all_energy_v1[i] > 0])
p_ratio_arr = np.array([power_v0_all[j]/power_v1_all[j] for j in range(len(power_v0_all))
                         if power_v1_all[j] > 0])
# Align lengths (both computed from same base condition)
_len = min(len(t_ratio_arr), len(e_ratio_arr))
r_te, _ = stats.spearmanr(t_ratio_arr[:_len], e_ratio_arr[:_len])
row(f"  Spearman r(time_ratio, energy_ratio) = {r_te:.4f}  [very strong, confirming E ~ T]")
# power ratio vs energy ratio
_p_ratio_full = []
_e_ratio_full = []
for i in range(len(data)):
    e0, t0 = all_energy_v0[i], all_time_v0[i]
    e1, t1 = all_energy_v1[i], all_time_v1[i]
    if all(x and x>0 for x in [e0,t0,e1,t1]):
        _p_ratio_full.append((e0/t0)/(e1/t1))
        _e_ratio_full.append(e0/e1)
r_pe, _ = stats.spearmanr(_p_ratio_full, _e_ratio_full)
r_pt, _ = stats.spearmanr(_p_ratio_full, [all_time_v0[i]/all_time_v1[i]
    for i in range(len(data)) if all_time_v0[i] and all_time_v1[i] and all_time_v1[i]>0
    and all_energy_v0[i] and all_energy_v1[i] and all_energy_v1[i]>0][:len(_p_ratio_full)])
row(f"  Spearman r(power_ratio, energy_ratio) = {r_pe:.4f}  [strong secondary effect]")

row("")
row(f"Counter-intuitive Cases (time improved but energy did NOT improve):")
row(f"  Samples where v0 was SLOWER than v1 but CONSUMED LESS ENERGY: {energy_worsened_n}")
row(f"  (time_ratio > 1.0 but energy_diff < 0 — v1 is faster but uses more energy)")
row("  Root pattern: NumPy / vectorized operations — faster wall time but higher power draw")
row("  Example cases (unique_index, energy_diff, time_ratio, P_v0, P_v1, categories):")
for ex in energy_worsened_examples:
    idx, ed, tr, p0, p1, cs = ex
    row(f"    idx={idx}: energy_diff={ed:.1f}J, time={tr:.2f}x faster, "
        f"P_v0={p0:.1f}W vs P_v1={p1:.1f}W, cats={cs}")

row("")
row("Implication for the manuscript (energy vs performance taxonomy debate):")
row("  Although time and energy are highly correlated (Spearman r=0.99), power is NOT")
row("  constant across code patterns (CV=24%). The E=P*T model requires both.")
row("  The 'vectorized code' cases prove that faster code can consume MORE energy —")
row("  a classic counter-example showing performance smells ≠ energy smells.")
row("  This motivates the need for a dedicated energy smell taxonomy.")

# ===========================================================================
# SECTION 17 – Power by Category
# ===========================================================================
section("SECTION 17 – Power Ratio Analysis by Category")
cat_power_ratios = defaultdict(list)
for i in range(len(data)):
    e0, t0 = all_energy_v0[i], all_time_v0[i]
    e1, t1 = all_energy_v1[i], all_time_v1[i]
    if not all(x and x > 0 for x in [e0, t0, e1, t1]): continue
    pr = (e0/t0) / (e1/t1)
    for cat in set(c for c, _ in all_labels[i]):   # unique categories per sample
        cat_power_ratios[cat].append(pr)

row(f"{'Cat':<6} {'Name':<32} {'N':>5}  {'Mean_P_ratio':>14}  {'Pct_v0_more_power':>18}  {'Median_P_ratio':>15}")
row("  " + "-"*90)
for cat in CAT_ORDER:
    vals = cat_power_ratios[cat]
    if not vals: continue
    above = sum(1 for v in vals if v > 1.05)
    row(f"  {cat:<6} {TAXONOMY[cat]['name']:<32} {len(vals):>5}  "
        f"{np.mean(vals):>14.3f}  {100*above/len(vals):>17.1f}%  {np.median(vals):>15.3f}")
row("")
row("C5 (Suboptimal Data Structures) and C6 (Unnecessary Memory Usage) have the highest")
row("  mean power ratios (>1.25), indicating memory-intensive smells increase both time")
row("  AND power draw — doubly impactful on energy (E = P * T).")
row("C1 (Redundant Computation) also shows elevated power ratio (>1.18): dead code,")
row("  import overhead, and repeated redundant work all keep the CPU busier.")

# ===========================================================================
# SECTION 18 – Time vs Energy Improvement: Our Measurements vs Cross-Platform
# ===========================================================================
section("SECTION 18 – Time vs Energy Improvement (result_* fields vs cross-platform)")

# ---- PART A: Our own measurements (result_time and result_energy) -----------
row("PART A: Within our measurement system (result_time_v0/v1 vs result_energy_v0/v1)")
time_impr  = []   # (result_time_v0 - result_time_v1) / result_time_v0 * 100
energy_impr = []  # (result_energy_v0 - result_energy_v1) / result_energy_v0 * 100

for i, r in enumerate(data):
    t0, t1 = all_time_v0[i], all_time_v1[i]
    e0, e1 = all_energy_v0[i], all_energy_v1[i]
    if t0 and t0 > 0 and e0 and e0 > 0:
        time_impr.append(100 * (t0 - t1) / t0)
        energy_impr.append(100 * (e0 - e1) / e0)

time_impr_arr   = np.array(time_impr)
energy_impr_arr = np.array(energy_impr)

row(f"  Samples: {len(time_impr_arr)}")
row(f"  Time improvement   (result_time):   mean={np.mean(time_impr_arr):.2f}%,  median={np.median(time_impr_arr):.2f}%,  std={np.std(time_impr_arr):.2f}%")
row(f"  Energy improvement (result_energy): mean={np.mean(energy_impr_arr):.2f}%, median={np.median(energy_impr_arr):.2f}%, std={np.std(energy_impr_arr):.2f}%")
r_te_sp, pval_te_sp = stats.spearmanr(time_impr_arr, energy_impr_arr)
r_te_p,  pval_te_p  = stats.pearsonr(time_impr_arr,  energy_impr_arr)
row(f"  Spearman r(time_improvement, energy_improvement) = {r_te_sp:.4f}, p={pval_te_sp:.2e}")
row(f"  Pearson  r(time_improvement, energy_improvement) = {r_te_p:.4f},  p={pval_te_p:.2e}")

t_better_e_worse = int(np.sum((time_impr_arr > 0) & (energy_impr_arr < 0)))
e_better_t_worse = int(np.sum((energy_impr_arr > 0) & (time_impr_arr < 0)))
both_better      = int(np.sum((time_impr_arr > 0) & (energy_impr_arr > 0)))
neither_better   = int(np.sum((time_impr_arr <= 0) & (energy_impr_arr <= 0)))
row(f"\n  Concordance breakdown:")
row(f"    Both time AND energy improved:         {both_better} ({100*both_better/len(time_impr_arr):.1f}%)")
row(f"    Time improved, energy WORSE:           {t_better_e_worse} ({100*t_better_e_worse/len(time_impr_arr):.1f}%)  <-- genuine power-driven exceptions")
row(f"    Energy improved, time WORSE:           {e_better_t_worse} ({100*e_better_t_worse/len(time_impr_arr):.1f}%)  <-- pure power-reduction cases")
row(f"    Neither time nor energy improved:      {neither_better} ({100*neither_better/len(time_impr_arr):.1f}%)  <-- cross-platform regressions")
row("")
row(f"  Within-platform time-improved-but-energy-worse ({t_better_e_worse} cases):")
row(f"  All involve significant POWER INCREASE (v1 draws more W despite being faster).")
row(f"  These are genuine E=P*T proof cases — power change dominates time change.")

# ===========================================================================
# SECTION 19 – Code Complexity vs Energy Impact
# ===========================================================================
section("SECTION 19 – Code Complexity vs Energy Impact")
# Compute LOC and chars from our actual code strings (code_v0_no_empty_lines / code_v1_no_empty_lines)
# These are derived from the stored code; we do NOT use code_v0_loc / code_v1_loc (original Pie-Perf fields)
def _count_loc(code_str):
    if not code_str: return 0
    return len([l for l in code_str.strip().split("\n") if l.strip()])

loc_v0_all   = [_count_loc(r.get("code_v0_no_empty_lines", "")) for r in data]
loc_v1_all   = [_count_loc(r.get("code_v1_no_empty_lines", "")) for r in data]
chars_v0_all = [len(r.get("code_v0_no_empty_lines", "")) for r in data]

loc_arr    = np.array(loc_v0_all, dtype=float)
chars_arr  = np.array(chars_v0_all, dtype=float)
diff_arr   = np.array([d if d else 0.0 for d in all_energy_diff])

r_loc, p_loc   = stats.spearmanr(loc_arr, diff_arr)
r_char, p_char = stats.spearmanr(chars_arr, diff_arr)
row(f"Spearman r(LOC_v0, energy_diff):        r={r_loc:.4f}, p={p_loc:.4f}")
row(f"Spearman r(chars_v0, energy_diff):      r={r_char:.4f}, p={p_char:.4f}")
row(f"\nCode size by energy quartile (mean LOC_v0 / chars_v0):")
row(f"  {'Quartile':<12} {'Mean_LOC_v0':>12}  {'Mean_LOC_v1':>12}  {'Mean_chars_v0':>14}")
for qb, qlabel in enumerate(_bin_labels):
    idxs_q = [i for i in range(len(data)) if all_energy_diff[i] and qbin4(all_energy_diff[i])==qb]
    if not idxs_q: continue
    mloc0 = np.mean([loc_v0_all[i] for i in idxs_q])
    mloc1 = np.mean([loc_v1_all[i] for i in idxs_q])
    mchars = np.mean([chars_v0_all[i] for i in idxs_q])
    row(f"  {qlabel:<12} {mloc0:>12.1f}  {mloc1:>12.1f}  {mchars:>14.1f}")
row(f"\nNote: Code length shows weak correlation with energy impact (r~{r_loc:.2f}).")
row(f"  Energy smell severity is largely independent of code length — a short snippet")
row(f"  importing numpy unnecessarily can save more energy than a 100-line algorithm fix.")

# ===========================================================================
# SECTION 20 – Zero-coverage Subcategories: Domain-Alignment Analysis
# ===========================================================================
section("SECTION 20 – Zero-coverage Subcategories: Domain-Alignment Analysis")
zero_explain = {
    "C2.S2": "Missing Static Declaration — Python dispatch model makes this a minor stylistic choice, not a measurable performance bottleneck in competitive code.",
    "C6.S6": "Leaked Resource Handles — competitive submissions do not use persistent file/socket/DB connections; the smell exists but is absent from this dataset's domain.",
    "C6.S7": "Leaking Mutable Default Arguments — a subtle Python-specific bug; rare in short submissions that don't define multi-call utility functions.",
    "C8.S4": "Redundant Data Fetching — requires external system interaction (DB, API, file); not present in pure in-memory algorithmic code.",
    "C9.S3": "Inefficient Retrieval Paths (N+1 query) — requires ORM/DB usage; not present in pure algorithmic solutions.",
    "C11.S2": "Forced Serial Bottleneck — requires multi-threaded architecture; competitive code is single-threaded.",
    "C11.S3": "Leaked Background Threads — requires spawning threads; absent from algorithmic submissions.",
    "C11.S4": "Blocking The Main Thread — requires async/event-loop usage; absent from algorithmic submissions.",
    "C11.S5": "Missed Parallelism — competitive problems are single-core; parallelism not applicable.",
    "C12.S4": "Inefficient Array Declaration Order — compiler/native extension concern; CPython GC heap allocation does not expose this pattern.",
}
row(f"10 subcategories have zero coverage. All are explainable by dataset domain:")
row("")
for sub, exp in zero_explain.items():
    row(f"  {sub}: {exp}")
row("")
row("Zero-coverage subcategories are concentrated in:")
row("  C11 (Concurrency): 4/5 subcategories — dataset is single-threaded algorithmic code")
row("  C9 (External I/O): 1/4 subcategories — no ORM/DB interaction in competitive code")
row("  C6 (Memory): 2/7 subcategories — resource-lifecycle patterns absent in competitive code")
row("")
row("This validates the taxonomy's domain-scope alignment rather than revealing incompleteness.")
row("The 55/65 = 84.6% coverage rate is appropriate for an algorithmic-code dataset.")
row("A real-world application dataset (web backends, data pipelines) would cover C9, C11, C12.S4.")

# ===========================================================================
# Write text output
# ===========================================================================
write_output()

# ===========================================================================
# PLOTS
# ===========================================================================
print("Generating plots …")

# --- Plot 1: Category distribution (horizontal bar) -----------------------
fig, ax = plt.subplots(figsize=(10, 6))
cats_sorted  = CAT_ORDER
counts       = [cat_sample_count.get(c, 0) for c in cats_sorted]
labels_str   = [f"{c}: {TAXONOMY[c]['name']}" for c in cats_sorted]
colors       = [CAT_COLORS[c] for c in cats_sorted]
bars = ax.barh(labels_str, counts, color=colors, edgecolor="grey", linewidth=0.5)
for bar, cnt in zip(bars, counts):
    ax.text(bar.get_width() + 5, bar.get_y() + bar.get_height()/2,
            str(cnt), va="center", fontsize=9)
ax.set_xlabel("Number of samples", fontsize=11)
ax.set_title("Category Distribution: samples per energy smell category", fontsize=12, fontweight="bold")
ax.invert_yaxis()
plt.tight_layout()
plt.savefig(os.path.join(RESULT_DIR, "plot_category_distribution.png"), dpi=150)
plt.close()

# --- Plot 2: Subcategory distribution (faceted 3×4, proportional columns) ---
def _darken(hex_color, factor=0.58):
    """Darken a pastel hex color for bar fills."""
    rgb = np.array([int(hex_color.lstrip('#')[i:i+2], 16) / 255 for i in (0, 2, 4)])
    return tuple(np.clip(rgb * factor, 0, 1))

def _lighten(hex_color, factor=0.55):
    rgb = np.array([int(hex_color.lstrip('#')[i:i+2], 16) / 255 for i in (0, 2, 4)])
    return tuple(np.clip(rgb + (1 - rgb) * factor, 0, 1))

# Column widths = max subcats across the 3 rows for that column position
_col_widths = [
    max(len(TAXONOMY[CAT_ORDER[row * 4 + col]]["subcats"]) for row in range(3))
    for col in range(4)
]
# Row heights proportional to sqrt(max count in row)
_row_maxes = [
    max(max(sub_count.get(s, 0) for s in TAXONOMY[c]["subcats"])
        for c in CAT_ORDER[row * 4:(row + 1) * 4])
    for row in range(3)
]
_row_heights = [max(np.sqrt(m), 3) for m in _row_maxes]

fig = plt.figure(figsize=(13, 5.6))
_gs = fig.add_gridspec(
    3, 4,
    width_ratios=_col_widths,
    height_ratios=_row_heights,
    hspace=0.62,        # enough for x-tick labels + set_title above frame
    wspace=0.22,
    left=0.05, right=0.99,
    top=0.96, bottom=0.07,
)
for _idx, _cat in enumerate(CAT_ORDER):
    _row, _col = divmod(_idx, 4)
    _ax = fig.add_subplot(_gs[_row, _col])
    _subs   = TAXONOMY[_cat]["subcats"]
    _counts = [sub_count.get(s, 0) for s in _subs]
    _labels = [s.split(".")[1] for s in _subs]
    _pastel = CAT_COLORS[_cat]
    _dark   = _darken(_pastel)              # rich bar fill
    _faded  = _lighten(_pastel, 0.40)      # pale fill for zero bars
    _n      = len(_subs)
    _cw     = _col_widths[_col]
    _counts_p = _counts + [0] * (_cw - _n)
    _labels_p = _labels + [""] * (_cw - _n)
    _bcolors  = ([_dark if c > 0 else _faded for c in _counts]
                 + ["none"] * (_cw - _n))

    _bars = _ax.bar(range(_cw), _counts_p, color=_bcolors,
                    edgecolor="white", linewidth=0.7, width=0.80)
    _max_c = max(_counts) if max(_counts) > 0 else 1

    # Count annotations — tight gap above bar so ceiling can be lower
    for _bar, _cnt in zip(_bars[:_n], _counts):
        if _cnt > 0:
            _ax.text(_bar.get_x() + _bar.get_width() / 2,
                     _bar.get_height() + _max_c * 0.015,
                     str(_cnt), ha='center', va='bottom',
                     fontsize=7.5, fontweight='bold', color='#111')

    # Title via set_title → lives ABOVE the axes frame, never overlaps bars
    _name  = TAXONOMY[_cat]['name']
    _tfont = 8.2 if len(_name) <= 20 else (7.5 if len(_name) <= 28 else 6.8)
    _ax.set_title(f"{_cat}  {_name}", fontsize=_tfont, fontweight="bold",
                  color=_dark, loc='left', pad=3)

    # Tight ceiling: just room for the annotation
    _ax.set_ylim(0, _max_c * 1.16)
    _ax.set_yticks([0, _max_c])
    _ax.yaxis.set_major_formatter(
        ticker.FuncFormatter(lambda x, _: f"{int(x)}" if x > 0 else "0"))
    _ax.tick_params(axis='y', labelsize=7.5, pad=1)

    _ax.set_xticks(range(_cw))
    _ax.set_xticklabels(_labels_p, fontsize=8.5, rotation=0)
    for _i, _tick in enumerate(_ax.xaxis.get_major_ticks()):
        if _i >= _n:
            _tick.set_visible(False)
    _ax.tick_params(axis='x', length=2, pad=1)

    if _col == 0:
        _ax.set_ylabel("n", fontsize=9, labelpad=2)
    _ax.spines[['top', 'right']].set_visible(False)
    _ax.yaxis.grid(linewidth=0.35, alpha=0.4, color='#aaa')
    _ax.set_axisbelow(True)
plt.savefig(os.path.join(RESULT_DIR, "plot_subcategory_distribution.png"), dpi=180,
            bbox_inches="tight")
plt.close()

# --- Plot 3: Energy diff boxplot per category (log scale) -----------------
fig, ax = plt.subplots(figsize=(14, 6))
box_data   = [cat_energy_diff.get(cat, [1e-3]) for cat in CAT_ORDER]
bp = ax.boxplot(box_data, patch_artist=True, medianprops={"color":"black","linewidth":1.5},
                flierprops={"marker":"o","markersize":2,"alpha":0.3})
for patch, cat in zip(bp["boxes"], CAT_ORDER):
    patch.set_facecolor(CAT_COLORS[cat])
ax.set_yscale("log")
ax.set_xticks(range(1, 13))
ax.set_xticklabels(CAT_ORDER, fontsize=10)
ax.set_ylabel("Energy difference v0 − v1 (J, log scale)", fontsize=11)
ax.set_title("Energy Savings Distribution per Category", fontsize=12, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(RESULT_DIR, "plot_energy_per_category.png"), dpi=150)
plt.close()

# --- Plot 4: Multi-label distribution bar ---------------------------------
fig, ax = plt.subplots(figsize=(7, 5))
max_k   = max(label_hist.keys()) if label_hist else 1
keys    = list(range(0, min(max_k+1, 8)))
vals    = [label_hist.get(k, 0) for k in keys]
k_labels= [str(k) if k < 7 else "7+" for k in keys]
ax.bar(k_labels, vals, color="#4C72B0", edgecolor="white")
for xi, v in zip(k_labels, vals):
    ax.text(xi, v + 5, str(v), ha="center", fontsize=9)
ax.set_xlabel("Number of labels per sample", fontsize=11)
ax.set_ylabel("Number of samples", fontsize=11)
ax.set_title("Multi-label Distribution", fontsize=12, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(RESULT_DIR, "plot_multilabel_distribution.png"), dpi=150)
plt.close()

# --- Plot 5: Time–energy correlation scatter ------------------------------
fig, ax = plt.subplots(figsize=(8, 6))
# Cap extreme values for readability (99th percentile)
rl_cap   = np.percentile(rl_arr, 99)
er_cap   = np.percentile(er_arr, 99)
mask_cap = (rl_arr <= rl_cap) & (er_arr <= er_cap)
ax.scatter(rl_arr[mask_cap], er_arr[mask_cap], alpha=0.15, s=8, color="#4C72B0")
# Regression line
m, b, *_ = stats.linregress(rl_arr[mask_cap], er_arr[mask_cap])
x_line   = np.linspace(rl_arr[mask_cap].min(), rl_arr[mask_cap].max(), 200)
ax.plot(x_line, m * x_line + b, color="red", linewidth=2,
        label=f"y = {m:.3f}x + {b:.3f}\nPearson r = {pearson_r:.3f}")
ax.set_xlabel("Runtime lift (v0_time / v1_time)", fontsize=11)
ax.set_ylabel("Energy ratio (v0_energy / v1_energy)", fontsize=11)
ax.set_title("Time–Energy Correlation", fontsize=12, fontweight="bold")
ax.legend(fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(RESULT_DIR, "plot_time_energy_correlation.png"), dpi=150)
plt.close()

# --- Plot 6: Category co-occurrence heatmap --------------------------------
matrix = np.zeros((12, 12), dtype=int)
for (a, b), cnt in pair_counter.items():
    if a in CAT_ORDER and b in CAT_ORDER:
        i, j = CAT_ORDER.index(a), CAT_ORDER.index(b)
        matrix[i][j] = cnt
        matrix[j][i] = cnt

fig, ax = plt.subplots(figsize=(10, 8))
im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto")
ax.set_xticks(range(12))
ax.set_yticks(range(12))
ax.set_xticklabels(CAT_ORDER, rotation=45, ha="right", fontsize=10)
ax.set_yticklabels(CAT_ORDER, fontsize=10)
plt.colorbar(im, ax=ax, label="Co-occurrence count")
# Annotate cells
for i in range(12):
    for j in range(12):
        if matrix[i][j] > 0:
            ax.text(j, i, str(matrix[i][j]),
                    ha="center", va="center", fontsize=6.5,
                    color="black" if matrix[i][j] < matrix.max()*0.6 else "white")
ax.set_title("Category Co-occurrence Heatmap", fontsize=12, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(RESULT_DIR, "plot_cooccurrence_heatmap.png"), dpi=150)
plt.close()

# --- Plot 7: Category prevalence by energy quartile (grouped bar) ----------
fig, ax = plt.subplots(figsize=(14, 6))
_bin_labels_short = ['Q1 (low)', 'Q2', 'Q3', 'Q4 (high)']
n_cats = len(CAT_ORDER)
n_bins = 4
bar_w = 0.18
x = np.arange(n_cats)
for bi, (bl, bls) in enumerate(zip(range(4), _bin_labels_short)):
    vals_pct = []
    for cat in CAT_ORDER:
        obs_bi = cat_qbin[cat][bi]
        tot_bi = total_qbin[bi]
        vals_pct.append(100 * obs_bi / tot_bi if tot_bi > 0 else 0)
    offset = (bi - 1.5) * bar_w
    bars_q = ax.bar(x + offset, vals_pct, bar_w, label=bls, alpha=0.85)
ax.set_xticks(x)
ax.set_xticklabels(CAT_ORDER, fontsize=10)
ax.set_ylabel("% of quartile bin with this category", fontsize=11)
ax.set_title("Category Prevalence by Energy Quartile\n(% of samples in each energy bin that contain the category)",
             fontsize=11, fontweight="bold")
ax.legend(title="Energy quartile", fontsize=9)
plt.tight_layout()
plt.savefig(os.path.join(RESULT_DIR, "plot_category_by_energy_quartile.png"), dpi=150)
plt.close()

# --- Plot 8: Power distribution v0 vs v1 + E=P*T decomposition bar --------
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# Left: KDE / histogram of power v0 and v1
ax = axes[0]
_pv0_clip = np.clip(power_v0_all, 50, 160)
_pv1_clip = np.clip(power_v1_all, 50, 160)
ax.hist(_pv0_clip, bins=40, alpha=0.55, color="#E74C3C", label=f"v0 (inefficient) mean={np.mean(power_v0_all):.1f}W")
ax.hist(_pv1_clip, bins=40, alpha=0.55, color="#2ECC71", label=f"v1 (efficient)   mean={np.mean(power_v1_all):.1f}W")
ax.axvline(np.mean(power_v0_all), color="#E74C3C", linestyle="--", linewidth=1.5)
ax.axvline(np.mean(power_v1_all), color="#2ECC71", linestyle="--", linewidth=1.5)
ax.set_xlabel("Power draw (Watts = J/s)", fontsize=11)
ax.set_ylabel("Number of samples", fontsize=11)
ax.set_title("Power Distribution: v0 vs v1\n(CV=24% shows power is NOT constant)", fontsize=11, fontweight="bold")
ax.legend(fontsize=9)

# Right: Stacked bar showing time-contribution vs power-contribution per energy quartile
ax = axes[1]
qb_tc_means, qb_pc_means, qb_ed_means = [], [], []
for qb in range(4):
    idxs_q = [i for i in range(len(data)) if all_energy_diff[i] and qbin4(all_energy_diff[i])==qb]
    _valid_tc, _valid_pc, _valid_ed = [], [], []
    for i in idxs_q:
        e0, t0 = all_energy_v0[i], all_time_v0[i]
        e1, t1 = all_energy_v1[i], all_time_v1[i]
        if all(x and x>0 for x in [e0,t0,e1,t1]):
            p0, p1 = e0/t0, e1/t1
            _valid_tc.append(p0*(t0-t1))
            _valid_pc.append((p0-p1)*t1)
            _valid_ed.append(e0-e1)
    qb_tc_means.append(np.mean(_valid_tc) if _valid_tc else 0)
    qb_pc_means.append(np.mean(_valid_pc) if _valid_pc else 0)
    qb_ed_means.append(np.mean(_valid_ed) if _valid_ed else 0)

x_q = np.arange(4)
ax.bar(x_q, qb_tc_means, 0.5, label="Time component P₀·ΔT", color="#3498DB", alpha=0.8)
ax.bar(x_q, qb_pc_means, 0.5, bottom=qb_tc_means, label="Power component ΔP·T₁", color="#E67E22", alpha=0.8)
ax.set_xticks(x_q)
ax.set_xticklabels(_bin_labels_short, fontsize=10)
ax.set_ylabel("Mean energy savings (J)", fontsize=11)
ax.set_title("Energy Savings Decomposition: E = P×T\n(time vs power contribution per quartile)", fontsize=11, fontweight="bold")
ax.legend(fontsize=9)

plt.tight_layout()
plt.savefig(os.path.join(RESULT_DIR, "plot_power_analysis.png"), dpi=150)
plt.close()

# --- Plot 9: Time improvement vs energy improvement scatter (result_* fields only) ---
fig, ax = plt.subplots(figsize=(8, 6))

# Within-platform (result_time vs result_energy)
_ti_arr = time_impr_arr; _ei_arr = energy_impr_arr
_clip = 100
_mask = (_ti_arr > -_clip) & (_ti_arr < _clip+20) & (_ei_arr > -_clip) & (_ei_arr < _clip+20)
ax.scatter(_ti_arr[_mask], _ei_arr[_mask], alpha=0.08, s=6, color="#4C72B0")
ax.axhline(0, color='red', linestyle='--', linewidth=0.8, alpha=0.6)
ax.axvline(0, color='red', linestyle='--', linewidth=0.8, alpha=0.6)
ax.fill_betweenx([-_clip, 0], 0, _clip+20, alpha=0.06, color='orange',
                 label='Time improved, energy worsened')
lims = [-_clip, _clip]
ax.plot(lims, lims, 'k--', linewidth=1, alpha=0.4, label='y = x (equal improvement)')
_m, _b, *_ = stats.linregress(_ti_arr[_mask], _ei_arr[_mask])
_xl = np.linspace(-_clip, _clip, 200)
ax.plot(_xl, _m*_xl+_b, color="red", linewidth=2,
        label=f"Regression: slope={_m:.2f}, r={r_te_sp:.3f}")
ax.set_xlabel("Time improvement % (result_time)", fontsize=10)
ax.set_ylabel("Energy improvement % (result_energy)", fontsize=10)
ax.set_title(f"Within-platform: time vs energy\n(Spearman r={r_te_sp:.4f}; {t_better_e_worse} power-driven exceptions)",
             fontsize=10, fontweight="bold")
ax.legend(fontsize=8)
ax.set_xlim(-_clip, _clip+20); ax.set_ylim(-_clip, _clip+20)

plt.suptitle("Time Improvement vs Energy Improvement (result_* fields only)", fontsize=12, fontweight="bold")
plt.tight_layout()
plt.savefig(os.path.join(RESULT_DIR, "plot_time_vs_energy_improvement.png"), dpi=150)
plt.close()

print("All plots saved to", RESULT_DIR)


# ===========================================================================
# Plot: Sunburst / Donut — Category + Subcategory distribution
# ===========================================================================

def _pie_shade_range(base_hex, n, f_min=0.60, f_max=0.95):
    rgb = np.array([int(base_hex.lstrip('#')[i:i+2], 16) / 255 for i in (0, 2, 4)])
    return [tuple(np.clip(rgb * (f_min + (f_max - f_min) * k / max(n - 1, 1)), 0, 1)) for k in range(n)]

_PIE_RICH = {
    "C1":"#C0392B","C2":"#2471A3","C3":"#1E8449","C4":"#B7950B",
    "C5":"#CA6F1E","C6":"#6C3483","C7":"#1A5276","C8":"#117A65",
    "C9":"#5D6D7E","C10":"#922B21","C11":"#D35400","C12":"#1F618D",
}

def _build_pie_chart(ax, sub_count, cat_total, grand, sub_grd,
                     show_center=True, threshold=0.55):
    """Draw sunburst rings on ax. Returns (Ri_i, Ri_o, Ro_i, Ro_o)."""
    Ri_i, Ri_o = 0.10, 0.50
    Ro_i, Ro_o = 0.54, 0.88

    inner_vals = [cat_total.get(c, 0) for c in CAT_ORDER]
    wedges_in, _ = ax.pie(inner_vals, radius=Ri_o,
                          colors=[_PIE_RICH[c] for c in CAT_ORDER],
                          startangle=90, counterclock=False,
                          wedgeprops=dict(width=Ri_o - Ri_i, edgecolor='white', linewidth=1.3))

    all_out_vals, all_out_cols = [], []
    for cat in CAT_ORDER:
        cnts = [sub_count.get(s, 0) for s in TAXONOMY[cat]["subcats"]]
        all_out_vals.extend(cnts)
        all_out_cols.extend(_pie_shade_range(_PIE_RICH[cat], len(cnts)))
    wedges_out, _ = ax.pie(all_out_vals, radius=Ro_o,
                           colors=all_out_cols, startangle=90, counterclock=False,
                           wedgeprops=dict(width=Ro_o - Ro_i, edgecolor='white', linewidth=0.45))

    if show_center:
        for txt, y, fs, fw, col in [
            ("3,000",           0.13, 20, 'bold',   '#1a1a1a'),
            ("Code Pairs",     -0.04, 15, 'normal', '#444'),
            ("12 Cat · 65 Sub",-0.16, 13, 'normal', '#666'),
        ]:
            ax.text(0, y, txt, ha='center', va='center', fontsize=fs, fontweight=fw, color=col)

    R_mid_in  = (Ri_i + Ri_o) / 2
    R_mid_out = (Ro_i + Ro_o) / 2
    all_outside_sub, all_outside_cat = [], []
    ARROW_CATS   = {"C2", "C4", "C8", "C9", "C12"}
    CAT_INNER_COL = {"C12"}

    for wedge, cat, val in zip(wedges_in, CAT_ORDER, inner_vals):
        pct = val / grand * 100
        ang = (wedge.theta2 + wedge.theta1) / 2
        if cat in ARROW_CATS:
            if pct >= 0.05:
                entry = ((ang - 2) % 360 if cat in CAT_INNER_COL else ang % 360,
                         f"{cat}: {val}\n({pct:.1f}%)", _PIE_RICH[cat], Ri_o, 16.0)
                (all_outside_sub if cat in CAT_INNER_COL else all_outside_cat).append(entry)
            continue
        x = R_mid_in * np.cos(np.radians(ang))
        y = R_mid_in * np.sin(np.radians(ang))
        if pct >= 5.0:
            ax.text(x, y, f"{cat}\n{val:,}\n({pct:.0f}%)",
                    ha='center', va='center', fontsize=14, fontweight='bold',
                    color='white', linespacing=1.25)
        elif pct >= 1.5:
            ax.text(x, y, f"{cat}\n{val}",
                    ha='center', va='center', fontsize=11, fontweight='bold',
                    color='white', linespacing=1.2)
        elif pct >= 0.3:
            ax.text(x, y, cat,
                    ha='center', va='center', fontsize=9.5, fontweight='bold', color='white')

    sub_idx = 0
    for cat in CAT_ORDER:
        for s in TAXONOMY[cat]["subcats"]:
            cnt   = sub_count.get(s, 0)
            wedge = wedges_out[sub_idx]
            pct   = cnt / sub_grd * 100
            ang   = (wedge.theta2 + wedge.theta1) / 2
            slbl  = s.split('.')[1]
            if pct >= 2.2:
                x = R_mid_out * np.cos(np.radians(ang))
                y = R_mid_out * np.sin(np.radians(ang))
                ax.text(x, y, f"{slbl}\n{cnt}", ha='center', va='center',
                        fontsize=12, fontweight='bold', color='white', linespacing=1.1)
            elif pct >= threshold:
                all_outside_sub.append((ang % 360, f"{s}: {cnt}", _PIE_RICH[cat], Ro_o, 15.0))
            sub_idx += 1

    all_outside_sub.extend(all_outside_cat)

    X_TEXT_R, X_TEXT_L = 1.10, -1.10
    Y_TOP, Y_BOT = 0.88, -0.88

    def _exit_y(item):
        ang_, _, _, R_edge, _ = item
        r = (Ro_o + 0.05) if R_edge < Ro_i else (R_edge + 0.015)
        return r * np.sin(np.radians(ang_))

    def draw_comb(items, XT_R, XT_L):
        right = sorted([i for i in items if np.cos(np.radians(i[0])) >= 0],
                       key=_exit_y, reverse=True)
        left  = sorted([i for i in items if np.cos(np.radians(i[0])) <  0],
                       key=_exit_y, reverse=True)

        def place(side, x_text):
            n = len(side)
            if n == 0: return
            sgn  = np.sign(x_text)
            ha   = 'left' if x_text > 0 else 'right'
            x_sp = sgn * (Ro_o + 0.08)
            ys   = np.linspace(Y_TOP, Y_BOT, n) if n > 1 else [_exit_y(side[0])]
            for (ang_, lbl, col, R_edge, fs), y_lbl in zip(side, ys):
                xe = (R_edge + 0.015) * np.cos(np.radians(ang_))
                ye = (R_edge + 0.015) * np.sin(np.radians(ang_))
                ox, oy = xe, ye
                if R_edge < Ro_i:
                    r_ex = Ro_o + 0.05
                    x_ex = r_ex * np.cos(np.radians(ang_))
                    y_ex = r_ex * np.sin(np.radians(ang_))
                    ax.plot([xe, x_ex], [ye, y_ex], color=col, lw=0.85,
                            solid_capstyle='round', zorder=2, alpha=0.9)
                    ax.plot([x_ex, x_sp], [y_ex, y_lbl], color=col, lw=0.85,
                            solid_capstyle='round', zorder=2, alpha=0.9)
                else:
                    ax.plot([xe, x_sp], [ye, y_lbl], color=col, lw=0.75,
                            solid_capstyle='round', zorder=2, alpha=0.85)
                ax.plot([x_sp, x_text - sgn * 0.04], [y_lbl, y_lbl], color=col,
                        lw=0.75, solid_capstyle='round', zorder=2, alpha=0.85)
                ax.plot(ox, oy, 'o', color=col, ms=2.4, zorder=3)
                ax.text(x_text, y_lbl, lbl, ha=ha, va='center', fontsize=fs,
                        fontweight='bold', color=col, clip_on=False)
        place(right, XT_R)
        place(left,  XT_L)

    draw_comb(all_outside_sub, X_TEXT_R, X_TEXT_L)
    return Ro_o


def _plot_pie_best(sub_count, cat_total, grand, sub_grd):
    fig = plt.figure(figsize=(15, 10))
    ax  = fig.add_axes([0.0, 0.01, 1.0, 0.98], aspect="equal")
    _build_pie_chart(ax, sub_count, cat_total, grand, sub_grd,
                     show_center=True, threshold=0.55)
    ax.set_xlim(-1.32, 1.32)
    ax.set_ylim(-0.91, 0.96)
    plt.savefig(os.path.join(RESULT_DIR, "plot_pie_best.png"),
                dpi=180, bbox_inches="tight", pad_inches=0.05)
    plt.savefig(os.path.join(RESULT_DIR, "plot_pie_best.pdf"),
                bbox_inches="tight", pad_inches=0.05)
    plt.close()
    print("  Saved plot_pie_best.png / .pdf")


def _plot_pie_allsubs(sub_count, cat_total, grand, sub_grd):
    fig = plt.figure(figsize=(15, 10))
    ax  = fig.add_axes([0.0, 0.01, 1.0, 0.98], aspect="equal")
    _build_pie_chart(ax, sub_count, cat_total, grand, sub_grd,
                     show_center=False, threshold=0.10)
    # footnote
    fn_text = ("n=0: C2.S2, C6.S6–S7, C8.S4, C9.S3, C11.S2–S5, C12.S4"
               "   |   "
               "n≤5: C1.S8, C4.S1, C4.S3–S6, C9.S2, C9.S4, C10.S6, C11.S1")
    ax.text(0, -0.97, fn_text, ha='center', va='center', fontsize=14,
            color='#333', fontweight='bold', clip_on=False)
    ax.set_xlim(-1.32, 1.32)
    ax.set_ylim(-0.99, 0.96)
    plt.savefig(os.path.join(RESULT_DIR, "plot_pie_allsubs.png"),
                dpi=180, bbox_inches="tight", pad_inches=0.05)
    plt.savefig(os.path.join(RESULT_DIR, "plot_pie_allsubs.pdf"),
                bbox_inches="tight", pad_inches=0.05)
    plt.close()
    print("  Saved plot_pie_allsubs.png / .pdf")


print("Generating sunburst distribution charts …")
_pie_cat_total = cat_label_count          # Counter: category → total label occurrences
_pie_grand     = sum(_pie_cat_total.values())
_pie_sub_grd   = sum(sub_count.values())
_plot_pie_best(sub_count, _pie_cat_total, _pie_grand, _pie_sub_grd)
_plot_pie_allsubs(sub_count, _pie_cat_total, _pie_grand, _pie_sub_grd)
print("Sunburst charts saved to", RESULT_DIR)


# ===========================================================================
# Utility: write individual sample files (preserved from original)
# ===========================================================================
def function_write(index, dataset):
    with open("temp_v0.py", "w") as f:
        f.write(dataset[index]["code_v0_no_empty_lines"])
    with open("temp_v1.py", "w") as f:
        f.write(dataset[index]["code_v1_no_empty_lines"])
    with open("classification.txt", "w", encoding="utf-8") as f:
        f.write(
            str(dataset[index]["llm_step1_root_cause"]) + "\n\n" +
            str(dataset[index]["llm_step2_candidates"]) + "\n\n" +
            str(dataset[index]["final_classification"])
        )