#!/usr/bin/env python3
"""
Reproducibility Score Evaluation Script

SCORING RULES:
==============
| Type           | Availability | Accessibility | Linkability | License     |
|----------------|--------------|---------------|-------------|-------------|
| URL (repo)     | Check value  | Check HTTP    | 100% (N/A)  | Check API   |
| URL (non-repo) | Check value  | Check HTTP    | 100% (N/A)  | 100% (N/A)  |
| Resource       | Check value  | 100% (N/A)    | Check onto  | 100% (N/A)  |
| Literal        | Check value  | 100% (N/A)    | 100% (N/A)  | 100% (N/A)  |

KEY: Inapplicable = 100% (automatic pass, no penalty)

Author: Hassan Hussein
Date: January 2026

Usage:
    py evaluate_reproducibility.py --input orkg_contributions.json --output results/
"""

import json
import csv
import urllib.request
import urllib.error
import urllib.parse
import ssl
import argparse
import os
import statistics
import time
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class PropertyEval:
    """Evaluation for one property."""
    contribution_id: str
    paper_id: str
    paper_title: str
    predicate_id: str
    predicate_label: str
    object_id: str
    property_type: str
    value: str
    # Scores (0 or 100)
    availability: float
    availability_reason: str
    accessibility: float
    accessibility_reason: str
    linkability: float
    linkability_reason: str
    license: float
    license_reason: str
    # Extra
    repo_type: str = ""
    ontology_source: str = ""
    license_name: str = ""


@dataclass
class ContributionEval:
    """Evaluation for one contribution."""
    contribution_id: str
    paper_id: str
    paper_title: str
    num_properties: int
    availability: float
    accessibility: float
    linkability: float
    license: float
    overall: float
    tier: str
    properties: List[PropertyEval] = field(default_factory=list)


def api_request(url: str, timeout: int = 10) -> Optional[Dict]:
    """Make API request."""
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        req.add_header("Accept", "application/json")
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return json.loads(resp.read().decode('utf-8')) if resp.status == 200 else None
    except:
        return None


def check_url(url: str, timeout: int = 8) -> Tuple[bool, str]:
    """Check URL accessibility."""
    try:
        req = urllib.request.Request(url, method='HEAD')
        req.add_header("User-Agent", "Mozilla/5.0")
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return (True, f"HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        if e.code == 405:
            try:
                req = urllib.request.Request(url)
                req.add_header("User-Agent", "Mozilla/5.0")
                with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                    return (True, f"HTTP {resp.status}")
            except:
                pass
        return (False, f"HTTP {e.code}")
    except urllib.error.URLError as e:
        return (False, f"Error: {str(e.reason)[:30]}")
    except Exception as e:
        return (False, f"Error: {str(e)[:30]}")


def check_github(owner: str, repo: str) -> Tuple[bool, str, str]:
    """Check GitHub license. Returns (has_license, license_name, reason)."""
    resp = api_request(f"https://api.github.com/repos/{owner}/{repo}")
    if resp:
        lic = resp.get("license")
        if lic and lic.get("spdx_id") and lic.get("spdx_id") != "NOASSERTION":
            name = lic.get("name") or lic.get("spdx_id")
            return (True, name, f"License: {name}")
        if "id" in resp:
            return (False, "", "No license found")
    return (False, "", "API failed")


def check_zenodo(record_id: str) -> Tuple[bool, str, str]:
    """Check Zenodo license."""
    resp = api_request(f"https://zenodo.org/api/records/{record_id}")
    if resp:
        lic = resp.get("metadata", {}).get("license")
        if lic:
            name = lic.get("id") if isinstance(lic, dict) else str(lic)
            return (True, name, f"License: {name}")
        if "id" in resp:
            return (False, "", "No license")
    return (False, "", "API failed")


def check_license(repo_type: str, owner: str, repo: str) -> Tuple[bool, str, str]:
    """Check repo license."""
    if repo_type == "github":
        return check_github(owner, repo)
    elif repo_type == "zenodo":
        return check_zenodo(repo)
    return (False, "", f"Unsupported: {repo_type}")


def get_tier(score: float) -> str:
    if score >= 80: return "Excellent"
    if score >= 60: return "Good"
    if score >= 40: return "Fair"
    return "Poor"


def evaluate_contribution(contrib: Dict, check_access: bool, check_lic: bool) -> ContributionEval:
    """Evaluate one contribution."""
    props = contrib.get("reproducibility_properties", [])
    cid = contrib.get("contribution_id", "")
    pid = contrib.get("paper_id", "")
    ptitle = contrib.get("paper_title", "")
    
    avail_scores = []
    access_scores = []
    link_scores = []
    lic_scores = []
    evals = []
    
    for p in props:
        value = p.get("value", "")
        ptype = p.get("property_type", "literal")
        
        # Default: 100% for inapplicable (per paper: inapplicable scores 100%)
        avail, avail_r = 100.0, ""
        access, access_r = 100.0, "Inapplicable (not URL)"
        link, link_r = 100.0, "Inapplicable (not resource)"
        lic, lic_r = 100.0, "Inapplicable (not repo URL)"
        lic_name = ""
        
        # === AVAILABILITY (all types - always applicable) ===
        if value and value.strip() and value.lower() not in ["n/a", "none", "null"]:
            avail, avail_r = 100.0, "Valid: has value"
        else:
            avail, avail_r = 0.0, "Not Valid: empty/null"
        
        # === ACCESSIBILITY (URLs only - others = 100% inapplicable) ===
        if ptype == "url":
            if check_access:
                ok, reason = check_url(value)
                access = 100.0 if ok else 0.0
                access_r = f"Valid: {reason}" if ok else f"Not Valid: {reason}"
            else:
                access, access_r = 100.0, "Skipped"
        
        # === LINKABILITY (resources only - others = 100% inapplicable) ===
        if ptype == "resource":
            if p.get("is_ontology_linked"):
                link = 100.0
                link_r = f"Valid: linked to {p.get('ontology_source', 'ontology')}"
            else:
                link = 0.0
                link_r = f"Not Valid: internal ORKG resource {p.get('object_id', '?')}"
        
        # === LICENSE (repo URLs only - others = 100% inapplicable) ===
        if ptype == "url" and p.get("is_repo_url"):
            if check_lic:
                has_lic, name, reason = check_license(
                    p.get("repo_type", ""),
                    p.get("repo_owner", ""),
                    p.get("repo_name", "")
                )
                lic = 100.0 if has_lic else 0.0
                lic_r = f"Valid: {reason}" if has_lic else f"Not Valid: {reason}"
                lic_name = name
                time.sleep(0.2)
            else:
                lic, lic_r = 100.0, "Skipped"
        
        # Collect all scores (including 100% for inapplicable)
        avail_scores.append(avail)
        access_scores.append(access)
        link_scores.append(link)
        lic_scores.append(lic)
        
        evals.append(PropertyEval(
            contribution_id=cid, paper_id=pid, paper_title=ptitle,
            predicate_id=p.get("predicate_id", ""),
            predicate_label=p.get("predicate_label", ""),
            object_id=p.get("object_id", ""),
            property_type=ptype,
            value=value[:150],
            availability=avail, availability_reason=avail_r,
            accessibility=access, accessibility_reason=access_r,
            linkability=link, linkability_reason=link_r,
            license=lic, license_reason=lic_r,
            repo_type=p.get("repo_type", ""),
            ontology_source=p.get("ontology_source", ""),
            license_name=lic_name
        ))
    
    # Calculate trimmed means (per paper: remove highest and lowest if n >= 4)
    def calc_mean(scores):
        if not scores:
            return 100.0  # No properties = 100% (shouldn't happen)
        if len(scores) >= 4:
            # Trimmed mean: remove highest and lowest, average the rest
            return statistics.mean(sorted(scores)[1:-1])
        return statistics.mean(scores)
    
    avail_mean = calc_mean(avail_scores)
    access_mean = calc_mean(access_scores)
    link_mean = calc_mean(link_scores)
    lic_mean = calc_mean(lic_scores)
    
    # Overall = mean of the 4 pillar scores
    overall = statistics.mean([avail_mean, access_mean, link_mean, lic_mean])
    
    return ContributionEval(
        contribution_id=cid, paper_id=pid, paper_title=ptitle,
        num_properties=len(props),
        availability=avail_mean, accessibility=access_mean,
        linkability=link_mean, license=lic_mean,
        overall=overall, tier=get_tier(overall),
        properties=evals
    )


def run_evaluation(contribs: List[Dict], check_access: bool, check_lic: bool):
    """Run full evaluation."""
    results = []
    n = len(contribs)
    
    print(f"\n{'='*70}")
    print(f"EVALUATING {n} CONTRIBUTIONS")
    print(f"{'='*70}")
    print(f"  HTTP checks: {check_access}")
    print(f"  License API: {check_lic}")
    print(f"  Rule: Inapplicable = 100% (per paper)")
    print(f"  Trimmed mean: removes highest/lowest if n >= 4 properties")
    print(f"{'='*70}\n")
    
    print(f"{'ID':<12} {'#':>4} {'Avail':>7} {'Access':>7} {'Link':>7} {'Lic':>7} {'Overall':>8} Tier")
    print("-" * 72)
    
    t0 = time.time()
    
    for i, c in enumerate(contribs):
        t1 = time.time()
        r = evaluate_contribution(c, check_access, check_lic)
        results.append(r)
        dt = time.time() - t1
        
        print(f"{r.contribution_id:<12} {r.num_properties:>4} "
              f"{r.availability:>6.1f}% {r.accessibility:>6.1f}% "
              f"{r.linkability:>6.1f}% {r.license:>6.1f}% "
              f"{r.overall:>7.1f}% {r.tier:<10} ({dt:.1f}s)")
    
    print("-" * 72)
    print(f"Total: {time.time()-t0:.1f}s")
    
    return results, calc_stats(results)


def calc_stats(results: List[ContributionEval]) -> Dict:
    """Calculate statistics."""
    def stats(vals):
        return {
            "mean": round(statistics.mean(vals), 1),
            "std": round(statistics.stdev(vals), 1) if len(vals) > 1 else 0,
            "median": round(statistics.median(vals), 1),
            "min": round(min(vals), 1),
            "max": round(max(vals), 1)
        }
    
    avail = [r.availability for r in results]
    access = [r.accessibility for r in results]
    link = [r.linkability for r in results]
    lic = [r.license for r in results]
    overall = [r.overall for r in results]
    
    # Property-level
    all_props = [p for r in results for p in r.properties]
    urls = [p for p in all_props if p.property_type == "url"]
    resources = [p for p in all_props if p.property_type == "resource"]
    literals = [p for p in all_props if p.property_type == "literal"]
    repos = [p for p in urls if p.repo_type]
    
    url_ok = sum(1 for p in urls if p.accessibility == 100)
    res_ok = sum(1 for p in resources if p.linkability == 100)
    lic_ok = sum(1 for p in repos if p.license == 100)
    
    lic_types = {}
    for p in repos:
        if p.license_name:
            lic_types[p.license_name] = lic_types.get(p.license_name, 0) + 1
    
    n = len(results)
    return {
        "total_contributions": n,
        "timestamp": datetime.now().isoformat(),
        "pillars": {
            "availability": stats(avail),
            "accessibility": stats(access),
            "linkability": stats(link),
            "license": stats(lic),
            "overall": stats(overall)
        },
        "tiers": {
            "excellent": sum(1 for r in results if r.tier == "Excellent"),
            "good": sum(1 for r in results if r.tier == "Good"),
            "fair": sum(1 for r in results if r.tier == "Fair"),
            "poor": sum(1 for r in results if r.tier == "Poor")
        },
        "properties": {
            "total": len(all_props),
            "urls": len(urls),
            "resources": len(resources),
            "literals": len(literals),
            "repos": len(repos)
        },
        "url_accessibility": {
            "total": len(urls),
            "accessible": url_ok,
            "rate": round(100*url_ok/len(urls), 1) if urls else 100
        },
        "resource_linkability": {
            "total": len(resources),
            "linked": res_ok,
            "rate": round(100*res_ok/len(resources), 1) if resources else 100
        },
        "repo_license": {
            "total": len(repos),
            "licensed": lic_ok,
            "rate": round(100*lic_ok/len(repos), 1) if repos else 100,
            "types": lic_types
        }
    }


def print_report(s: Dict):
    """Print report."""
    p = s["pillars"]
    t = s["tiers"]
    pr = s["properties"]
    n = s["total_contributions"]
    
    print(f"\n{'='*70}")
    print("REPRODUCIBILITY EVALUATION REPORT")
    print(f"{'='*70}")
    print(f"\nContributions: {n}")
    print(f"Properties: {pr['total']} (URLs:{pr['urls']} Resources:{pr['resources']} Literals:{pr['literals']})")
    
    print(f"\n{'-'*70}")
    print("PILLAR SCORES")
    print(f"{'-'*70}")
    print(f"{'Pillar':<15} {'Mean':>8} {'Std':>8} {'Median':>8} {'Range':>12}")
    for name in ['availability', 'accessibility', 'linkability', 'license', 'overall']:
        x = p[name]
        label = name.upper() if name == 'overall' else name.capitalize()
        print(f"{label:<15} {x['mean']:>7.1f}% {x['std']:>7.1f}% {x['median']:>7.1f}% {x['min']:.0f}-{x['max']:.0f}%")
    
    print(f"\n{'-'*70}")
    print("TIERS")
    print(f"{'-'*70}")
    print(f"Excellent (≥80%): {t['excellent']:>3} ({100*t['excellent']/n:.1f}%)")
    print(f"Good (60-79%):    {t['good']:>3} ({100*t['good']/n:.1f}%)")
    print(f"Fair (40-59%):    {t['fair']:>3} ({100*t['fair']/n:.1f}%)")
    print(f"Poor (<40%):      {t['poor']:>3} ({100*t['poor']/n:.1f}%)")
    
    print(f"\n{'-'*70}")
    print("DETAILED ANALYSIS")
    print(f"{'-'*70}")
    ua = s["url_accessibility"]
    rl = s["resource_linkability"]
    rl2 = s["repo_license"]
    
    print(f"URL Accessibility: {ua['accessible']}/{ua['total']} ({ua['rate']}%)")
    print(f"Resource Linkability: {rl['linked']}/{rl['total']} ({rl['rate']}%)")
    print(f"Repo Licenses: {rl2['licensed']}/{rl2['total']} ({rl2['rate']}%)")
    if rl2['types']:
        print(f"  Top: {dict(list(sorted(rl2['types'].items(), key=lambda x:-x[1])[:5]))}")
    
    print(f"\n{'='*70}")


def export_summary(results: List[ContributionEval], path: str):
    """Export summary CSV."""
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Contribution_ID', 'Paper_ID', 'Paper_Title', 'Num_Props',
                    'Availability%', 'Accessibility%', 'Linkability%', 'License%',
                    'Overall%', 'Tier'])
        for r in results:
            w.writerow([r.contribution_id, r.paper_id, r.paper_title[:70],
                       r.num_properties,
                       f"{r.availability:.1f}", f"{r.accessibility:.1f}",
                       f"{r.linkability:.1f}", f"{r.license:.1f}",
                       f"{r.overall:.1f}", r.tier])


def export_detailed(results: List[ContributionEval], path: str):
    """Export detailed CSV."""
    with open(path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Contribution_ID', 'Paper_ID', 'Paper_Title',
                    'Predicate_ID', 'Predicate_Label', 'Object_ID', 'Property_Type', 'Value',
                    'Availability%', 'Avail_Reason',
                    'Accessibility%', 'Access_Reason',
                    'Linkability%', 'Link_Reason',
                    'License%', 'Lic_Reason',
                    'Repo_Type', 'Ontology_Source', 'License_Name'])
        for r in results:
            for p in r.properties:
                w.writerow([p.contribution_id, p.paper_id, p.paper_title[:50],
                           p.predicate_id, p.predicate_label,
                           p.object_id, p.property_type, p.value[:80],
                           f"{p.availability:.0f}", p.availability_reason,
                           f"{p.accessibility:.0f}", p.accessibility_reason,
                           f"{p.linkability:.0f}", p.linkability_reason,
                           f"{p.license:.0f}", p.license_reason,
                           p.repo_type, p.ontology_source, p.license_name])


def export_latex(s: Dict, path: str):
    """Export LaTeX tables."""
    p = s["pillars"]
    t = s["tiers"]
    n = s["total_contributions"]
    ua = s["url_accessibility"]
    rl = s["resource_linkability"]
    rl2 = s["repo_license"]
    
    latex = f"""% Reproducibility Evaluation Results
% Generated: {s["timestamp"]}
% Rule: Inapplicable = 100% (automatic pass)

\\begin{{table}}[htbp]
\\centering
\\caption{{Reproducibility Score Results (n={n})}}
\\label{{tab:repro-scores}}
\\begin{{tabular}}{{lcccc}}
\\toprule
\\textbf{{Pillar}} & \\textbf{{Mean}} & \\textbf{{Std}} & \\textbf{{Median}} & \\textbf{{Range}} \\\\
\\midrule
Availability & {p['availability']['mean']:.1f}\\% & {p['availability']['std']:.1f} & {p['availability']['median']:.1f} & {p['availability']['min']:.0f}--{p['availability']['max']:.0f} \\\\
Accessibility & {p['accessibility']['mean']:.1f}\\% & {p['accessibility']['std']:.1f} & {p['accessibility']['median']:.1f} & {p['accessibility']['min']:.0f}--{p['accessibility']['max']:.0f} \\\\
Linkability & {p['linkability']['mean']:.1f}\\% & {p['linkability']['std']:.1f} & {p['linkability']['median']:.1f} & {p['linkability']['min']:.0f}--{p['linkability']['max']:.0f} \\\\
License & {p['license']['mean']:.1f}\\% & {p['license']['std']:.1f} & {p['license']['median']:.1f} & {p['license']['min']:.0f}--{p['license']['max']:.0f} \\\\
\\midrule
\\textbf{{Overall}} & {p['overall']['mean']:.1f}\\% & {p['overall']['std']:.1f} & {p['overall']['median']:.1f} & {p['overall']['min']:.0f}--{p['overall']['max']:.0f} \\\\
\\bottomrule
\\end{{tabular}}
\\end{{table}}

\\begin{{table}}[htbp]
\\centering
\\caption{{Property-Level Pass Rates}}
\\label{{tab:property-rates}}
\\begin{{tabular}}{{lccc}}
\\toprule
\\textbf{{Check}} & \\textbf{{Applicable}} & \\textbf{{Pass}} & \\textbf{{Rate}} \\\\
\\midrule
URL Accessibility & {ua['total']} & {ua['accessible']} & {ua['rate']}\\% \\\\
Resource Linkability & {rl['total']} & {rl['linked']} & {rl['rate']}\\% \\\\
Repository License & {rl2['total']} & {rl2['licensed']} & {rl2['rate']}\\% \\\\
\\bottomrule
\\end{{tabular}}
\\end{{table}}

\\begin{{table}}[htbp]
\\centering
\\caption{{Reproducibility Tier Distribution}}
\\label{{tab:repro-tiers}}
\\begin{{tabular}}{{lcc}}
\\toprule
\\textbf{{Tier}} & \\textbf{{Count}} & \\textbf{{Percent}} \\\\
\\midrule
Excellent ($\\geq$80\\%) & {t['excellent']} & {100*t['excellent']/n:.1f}\\% \\\\
Good (60--79\\%) & {t['good']} & {100*t['good']/n:.1f}\\% \\\\
Fair (40--59\\%) & {t['fair']} & {100*t['fair']/n:.1f}\\% \\\\
Poor ($<$40\\%) & {t['poor']} & {100*t['poor']/n:.1f}\\% \\\\
\\bottomrule
\\end{{tabular}}
\\end{{table}}
"""
    with open(path, 'w') as f:
        f.write(latex)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", required=True)
    parser.add_argument("--output", "-o", default="results")
    parser.add_argument("--skip-accessibility", action="store_true")
    parser.add_argument("--skip-licenses", action="store_true")
    args = parser.parse_args()
    
    os.makedirs(args.output, exist_ok=True)
    
    print("=" * 70)
    print("REPRODUCIBILITY EVALUATION")
    print("=" * 70)
    print(f"Input: {args.input}")
    print(f"Output: {args.output}/")
    
    with open(args.input, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    contribs = data.get("contributions", [])
    meta = data.get("metadata", {})
    
    print(f"\nLoaded {len(contribs)} contributions")
    if meta.get("property_distribution"):
        print(f"  Distribution: {meta['property_distribution']}")
    
    results, stats = run_evaluation(
        contribs,
        check_access=not args.skip_accessibility,
        check_lic=not args.skip_licenses
    )
    
    print_report(stats)
    
    # Export
    export_summary(results, os.path.join(args.output, "scores.csv"))
    export_detailed(results, os.path.join(args.output, "detailed.csv"))
    with open(os.path.join(args.output, "statistics.json"), 'w') as f:
        json.dump(stats, f, indent=2)
    export_latex(stats, os.path.join(args.output, "tables.tex"))
    
    print(f"\n✓ Saved: scores.csv, detailed.csv, statistics.json, tables.tex")


if __name__ == "__main__":
    main()
