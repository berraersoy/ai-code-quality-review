# Evaluation Framework: AI-Assisted Code Quality Review

This directory contains the experimental evaluation framework for comparing **Static Analysis**, **LLM-Based Analysis**, and **Hybrid Analysis**.

---

## 1. Ground Truth Definition

In academic defect detection research, **Ground Truth** represents the set of verified, genuine defects and quality issues present in the source code under test.

### Why Analyzer Output Cannot Be Treated as Ground Truth
- Static analysis tools (such as Ruff, Bandit, and Radon) produce automated heuristics that may include false alarms or miss complex logical defects.
- Large Language Models (LLMs) may hallucinate non-existent issues or overlook subtle vulnerabilities.
- **Treating either system's predictions as ground truth creates circular reasoning and invalidates scientific evaluation.**
- Therefore, ground truth in this project is stored in `evaluation_dataset/ground_truth.json` as **independently curated human labels**.

---

## 2. Evaluation Metrics

Predictions from each analysis mode are matched against ground-truth items using one-to-one bipartite matching.

| Metric | Definition | Interpretation |
| :--- | :--- | :--- |
| **True Positive (TP)** | Predicted finding that correctly matches a real ground-truth issue | Genuine defects detected |
| **False Positive (FP)** | Predicted finding that does NOT match any ground-truth issue | False alarms raised by analyzer |
| **False Negative (FN)** | Ground-truth defect that was NOT detected by the analyzer | Missed defects |

### Mathematical Formulations

$$\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}}$$

- Measures the accuracy of reported findings (how many reported issues are genuine).
- When $\text{TP} + \text{FP} = 0$, precision is defined as $0.0$.

$$\text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}}$$

- Measures defect coverage (how many genuine defects were successfully found).
- When $\text{TP} + \text{FN} = 0$, recall is defined as $0.0$.

$$\text{F1 Score} = 2 \times \frac{\text{Precision} \times \text{Recall}}{\text{Precision} + \text{Recall}}$$

- Harmonic mean of Precision and Recall, balancing false alarms against missed defects.
- When $\text{Precision} + \text{Recall} = 0$, F1 is defined as $0.0$.

---

## 3. Dataset-Level Aggregation (Micro-Averaging)

When calculating metrics across multiple source files:
1. **Raw counts ($\sum \text{TP}$, $\sum \text{FP}$, $\sum \text{FN}$) are accumulated across all files first.**
2. Overall Precision, Recall, and F1 are calculated from the accumulated totals.
3. **Per-file F1 scores are never averaged directly**, avoiding skew from small sample sizes.

---

## 4. Comparing Static, LLM, and Hybrid Analysis

Each file is independently reviewed under three modes:
1. **Static Analysis**: Ruff (syntax, style, control flow) + Bandit (security) + Radon (complexity).
2. **LLM-Only Analysis**: Zero-shot Python reviewer prompt evaluated independently without static tool hints.
3. **Hybrid Analysis**: One-to-one confirmation matcher combining static and LLM findings into hybrid and unique items.

> **Academic Note**: We make **no claim** that hybrid analysis is inherently superior to static or LLM-only analysis. Relative effectiveness (precision, recall, and F1 trade-offs) must be determined empirically through labeled benchmark datasets.

---

## 5. Mock vs. Real Gemini Evaluation

- **Mock LLM Mode (`--provider mock`)**:
  - Intended solely for deterministic testing, CI/CD, and pipeline verification.
  - Returns hardcoded rule-based findings for controlled sample files.
  - **Must NOT be used to report final LLM review accuracy in research papers or experimental reports.**
- **Real Gemini Mode (`--provider gemini`)**:
  - Queries Google Gemini (`gemini-3.8-flash`) via API.
  - Subject to network availability and transient service loads.
  - Must be run against human-verified ground-truth datasets for actual empirical evaluation.
