# ORKG Reproducibility Score Evaluation

Implementation of the four-pillar reproducibility assessment framework for scholarly knowledge graphs, as described in our ICADL 2023 paper.

📄 **Paper:** [Increasing Reproducibility in Science by Interlinking Semantic Artifact Descriptions in a Knowledge Graph](https://link.springer.com/chapter/10.1007/978-981-99-8088-8_19)  
📚 **DOI:** [10.1007/978-981-99-8088-8_19](https://doi.org/10.1007/978-981-99-8088-8_19)  
💻 **Repository:** [github.com/Webo1980/orkg-reproducibility-score](https://github.com/Webo1980/orkg-reproducibility-score)

---

## Overview

This repository provides tools to evaluate the reproducibility of scientific contributions in the [Open Research Knowledge Graph (ORKG)](https://orkg.org) using four pillars:

| Pillar | What it Measures |
|--------|------------------|
| **Availability** | Are artifact references provided? |
| **Accessibility** | Are URLs reachable (HTTP 200)? |
| **Linkability** | Are resources linked to trusted ontologies? |
| **License** | Do repositories have open licenses? |

---

## Repository Structure

```
orkg-reproducibility-score/
├── collect_orkg_data.py      # Data collection script
├── evaluate_reproducibility.py # Evaluation script
├── README.md
├── LICENSE
├── data/                      # Collected ORKG data
│   └── orkg_contributions.json
└── results/                   # Evaluation outputs
    ├── scores.csv             # Contribution-level scores
    ├── detailed.csv           # Property-level evaluation
    ├── statistics.json        # Aggregate statistics
    └── tables.tex             # LaTeX tables for thesis
```

---

## Scripts

### 1. `collect_orkg_data.py` - Data Collection

Collects contributions from the ORKG API with reproducibility-relevant properties. Uses **stratified sampling** to ensure balanced representation across property types.

**Features:**
- Fetches contributions with source code, datasets, benchmarks, etc.
- Classifies properties into 5 types: `url_repo`, `url_other`, `resource_onto`, `resource_internal`, `literal`
- Ensures minimum representation per type for valid statistical evaluation
- Detects repository URLs (GitHub, GitLab, Zenodo, Figshare, etc.)
- Identifies ontology-linked resources (Wikidata, DBpedia, OBO, etc.)

**Usage:**
```bash
# Default: collect until 40 minimum per property type (~200 contributions)
python collect_orkg_data.py --output data/orkg_contributions.json

# Custom minimum per type
python collect_orkg_data.py --output data/orkg_contributions.json --min-per-type 20
```

### 2. `evaluate_reproducibility.py` - Evaluation

Evaluates collected contributions across the four reproducibility pillars using the methodology from the paper.

**Features:**
- Implements Valid/Inapplicable/Not Valid scoring (per paper methodology)
- Uses trimmed mean to remove outliers (for n≥4 properties)
- Checks URL accessibility via HTTP requests
- Queries GitHub/GitLab APIs for license detection
- Generates detailed reports and LaTeX tables

**Usage:**
```bash
# Full evaluation (with HTTP and license checks)
python evaluate_reproducibility.py --input data/orkg_contributions.json --output results/

# Fast evaluation (skip network checks)
python evaluate_reproducibility.py --input data/orkg_contributions.json --output results/ --skip-accessibility --skip-licenses
```

---

## Scoring Methodology

### Three States for Each Property-Pillar Combination

| State | Score | Meaning |
|-------|-------|---------|
| **Valid** | 100% | Property meets the pillar criteria |
| **Inapplicable** | 100% | Property type cannot be evaluated for this pillar |
| **Not Valid** | 0% | Property fails the pillar criteria |

### Pillar Applicability Rules

| Pillar | Applicable To | Valid (100%) | Inapplicable (100%) | Not Valid (0%) |
|--------|---------------|--------------|---------------------|----------------|
| **Availability** | All types | Has non-empty value | — | Empty/null |
| **Accessibility** | URLs only | HTTP 200 response | Non-URL types | HTTP error |
| **Linkability** | Resources only | Linked to ontology | Non-resource types | Internal ORKG ID |
| **License** | Repo URLs only | Has open license | Non-repo URL types | No license found |

### Trimmed Mean (Outlier Removal)

For each pillar, the score is calculated using a **trimmed mean**:

```
If n >= 4 properties:
    Sort scores, remove highest and lowest value
    Pillar score = mean of remaining values
Else:
    Pillar score = simple mean

Overall score = mean(Availability, Accessibility, Linkability, License)
```

### Design Rationale: Inapplicable = 100%

A key design decision concerns the treatment of inapplicable properties. When a property cannot be meaningfully evaluated for a particular pillar, it receives a score of 100% rather than being excluded. This reflects the principle that a contribution should not be penalized for properties that fall outside the scope of a particular quality dimension.

For example, a literal value (e.g., a textual description) cannot be tested for URL accessibility. Excluding such properties would cause contributions with diverse property types to be evaluated only on a small subset, potentially yielding misleading scores.

### Tier Classification

| Tier | Score Range |
|------|-------------|
| Excellent | ≥80% |
| Good | 60-79% |
| Fair | 40-59% |
| Poor | <40% |

---

## Evaluation Results

### Dataset

- **Contributions:** 92
- **Properties:** 586
  - URLs: 113 (url_repo: 81, url_other: 32)
  - Resources: 217 (resource_onto: 22, resource_internal: 195)
  - Literals: 256

### Pillar Scores

| Pillar | Mean | Std | Median | Range |
|--------|------|-----|--------|-------|
| Availability | 100.0% | 0.0% | 100.0% | 100-100% |
| Accessibility | 98.8% | 10.4% | 100.0% | 0-100% |
| Linkability | 77.1% | 32.3% | 100.0% | 0-100% |
| License | 96.1% | 12.8% | 100.0% | 50-100% |
| **Overall** | **93.0%** | 9.4% | 100.0% | 75-100% |

### Tier Distribution

| Tier | Count | Percentage |
|------|-------|------------|
| Excellent (≥80%) | 76 | 82.6% |
| Good (60-79%) | 16 | 17.4% |
| Fair (40-59%) | 0 | 0.0% |
| Poor (<40%) | 0 | 0.0% |

### Property-Level Success Rates

For more direct interpretation, the property-level success rates show actual compliance:

| Metric | Success Rate | Details |
|--------|--------------|---------|
| URL Accessibility | 92.9% (105/113) | URLs returning HTTP 200 |
| Resource Linkability | 10.1% (22/217) | Resources linked to external ontologies |
| Repository Licenses | 34.6% (28/81) | Repos with detectable open licenses |

**Top Licenses Detected:**
- MIT License: 11
- Apache License 2.0: 8
- BSD 3-Clause: 4
- GNU GPL v2.0: 2
- BSD 2-Clause: 2

### Interpreting the Gap

The difference between pillar scores and property-level success rates reflects the methodology's design:

| Metric | Actual Success | Pillar Score | Gap |
|--------|----------------|--------------|-----|
| URL Accessibility | 92.9% | 98.8% | +5.9% |
| Resource Linkability | 10.1% | 77.1% | +67.0% |
| Repository Licenses | 34.6% | 96.1% | +61.5% |

The Linkability and License pillars show large gaps because most properties are inapplicable (literals, non-repo URLs) and score 100%. The property-level success rates provide actionable insights for improving reproducibility practices.

---

## Output Files

After running the evaluation, results are saved in the `results/` directory:

| File | Description |
|------|-------------|
| `scores.csv` | Contribution-level scores (one row per contribution) |
| `detailed.csv` | Property-level evaluation with reasons (one row per property) |
| `statistics.json` | Aggregate statistics (means, std, medians, ranges) |
| `tables.tex` | LaTeX tables ready for thesis/paper inclusion |

---

## Requirements

- Python 3.6+
- No external dependencies (uses standard library only)
- Internet access for ORKG API, URL checks, and license detection

---

## Quick Start

```bash
# Clone the repository
git clone https://github.com/Webo1980/orkg-reproducibility-score.git
cd orkg-reproducibility-score

# Collect data from ORKG (default: ~200 contributions)
python collect_orkg_data.py --output data/orkg_contributions.json

# Run evaluation
python evaluate_reproducibility.py --input data/orkg_contributions.json --output results/

# View results
cat results/statistics.json
```

---

## Citation

If you use this code in your research, please cite:

```bibtex
@inproceedings{hussein_reproducibility_2023,
  author    = {Hussein, Hassan and Farfar, Kheir Eddine and Oelen, Allard and Karras, Oliver and Auer, S{\"o}ren},
  title     = {Increasing Reproducibility in Science by Interlinking Semantic Artifact Descriptions in a Knowledge Graph},
  booktitle = {From Born-Physical to Born-Virtual: Augmenting Intelligence in Digital Libraries},
  series    = {Lecture Notes in Computer Science},
  volume    = {14458},
  pages     = {220--229},
  publisher = {Springer},
  year      = {2023},
  doi       = {10.1007/978-981-99-8088-8_19},
  url       = {https://link.springer.com/chapter/10.1007/978-981-99-8088-8_19}
}
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

This work is part of the [Open Research Knowledge Graph (ORKG)](https://orkg.org) project at [TIB - Leibniz Information Centre for Science and Technology](https://www.tib.eu/).
