#!/usr/bin/env python3
"""
ORKG Data Collection Script for Reproducibility Score Evaluation

Collects a BALANCED dataset with at least 20% of each property type:
- URL (repo)        → for License evaluation
- URL (non-repo)    → for Accessibility evaluation
- Resource (onto)   → for Linkability evaluation (positive cases)
- Resource (internal) → for Linkability evaluation (negative cases)
- Literal           → for Availability baseline

Author: Hassan Hussein
Date: January 2026

Usage:
    py collect_orkg_data.py --output orkg_contributions.json --min-per-type 40
"""

import json
import urllib.request
import ssl
import argparse
import time
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple


ORKG_API_BASE = "https://orkg.org/api"

# Repository URL patterns
REPO_PATTERNS = [
    (r'github\.com/([^/]+)/([^/\s\?#]+)', 'github'),
    (r'gitlab\.com/([^/]+)/([^/\s\?#]+)', 'gitlab'),
    (r'bitbucket\.org/([^/]+)/([^/\s\?#]+)', 'bitbucket'),
    (r'zenodo\.org/record/(\d+)', 'zenodo'),
    (r'doi\.org/10\.5281/zenodo\.(\d+)', 'zenodo'),
    (r'huggingface\.co/([^/]+)/([^/\s\?#]+)', 'huggingface'),
]

# Ontology prefixes
ONTOLOGY_PREFIXES = [
    ("wikidata:", "wikidata"), ("wd:", "wikidata"),
    ("http://www.wikidata.org/", "wikidata"), ("https://www.wikidata.org/", "wikidata"),
    ("http://purl.org/", "purl"), ("https://purl.org/", "purl"),
    ("http://www.w3.org/", "w3"), ("https://www.w3.org/", "w3"),
    ("http://schema.org/", "schema.org"), ("https://schema.org/", "schema.org"),
    ("http://dbpedia.org/", "dbpedia"), ("https://dbpedia.org/", "dbpedia"),
    ("doi:", "doi"), ("orcid:", "orcid"),
]

# Reproducibility keywords
REPRO_KEYWORDS = [
    "source code", "code", "implementation", "repository", "github",
    "dataset", "data", "benchmark", "model", "method", "url",
    "download", "license", "software", "script", "notebook",
    "framework", "library", "tool", "approach", "technique", "algorithm"
]


def extract_repo_info(url: str) -> Optional[Tuple[str, str, str]]:
    """Extract repo info from URL."""
    if not url:
        return None
    for pattern, repo_type in REPO_PATTERNS:
        match = re.search(pattern, url, re.IGNORECASE)
        if match:
            if repo_type == 'zenodo':
                return (repo_type, 'zenodo', match.group(1))
            return (repo_type, match.group(1), re.sub(r'\.git$', '', match.group(2)))
    return None


def get_ontology_source(obj_id: str, value: str) -> Optional[str]:
    """Check if linked to ontology."""
    for prefix, source in ONTOLOGY_PREFIXES:
        if prefix.lower() in obj_id.lower() or prefix.lower() in value.lower():
            return source
    return None


def make_request(url: str, is_papers: bool = False) -> Optional[Dict]:
    """Make API request."""
    try:
        request = urllib.request.Request(url)
        request.add_header("User-Agent", "Mozilla/5.0")
        if is_papers:
            request.add_header("Content-Type", "application/vnd.orkg.paper.v2+json;charset=UTF-8")
            request.add_header("Accept", "application/vnd.orkg.paper.v2+json")
        else:
            request.add_header("Accept", "application/json")
        context = ssl.create_default_context()
        with urllib.request.urlopen(request, timeout=30, context=context) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return None


def test_connection():
    """Test API connection."""
    print("Testing ORKG API...")
    result = make_request(f"{ORKG_API_BASE}/papers?size=1", is_papers=True)
    if result:
        total = result.get('page', {}).get('total_elements', '?')
        print(f"  ✓ Connected - {total} papers available")
        return True
    print("  ✗ Connection failed")
    return False


def is_repro_relevant(label: str) -> bool:
    """Check if predicate is reproducibility relevant."""
    return any(kw in label.lower() for kw in REPRO_KEYWORDS)


def process_property(stmt: Dict) -> Dict:
    """Process a single statement into property info."""
    pred = stmt.get("predicate", {})
    obj = stmt.get("object", {})
    
    pred_label = pred.get("label", "")
    value = str(obj.get("label", ""))
    obj_id = str(obj.get("id", ""))
    obj_class = obj.get("_class", "literal")
    
    # Determine type
    is_url = value.startswith(('http://', 'https://'))
    
    if is_url:
        prop_type = "url"
        repo_info = extract_repo_info(value)
        is_repo = repo_info is not None
        onto_source = None
    elif obj_class == "resource":
        prop_type = "resource"
        repo_info = None
        is_repo = False
        onto_source = get_ontology_source(obj_id, value)
    else:
        prop_type = "literal"
        repo_info = None
        is_repo = False
        onto_source = None
    
    return {
        "predicate_id": pred.get("id"),
        "predicate_label": pred_label,
        "object_id": obj_id,
        "object_class": obj_class,
        "property_type": prop_type,
        "value": value,
        "is_url": is_url,
        "is_repo_url": is_repo,
        "repo_type": repo_info[0] if repo_info else None,
        "repo_owner": repo_info[1] if repo_info else None,
        "repo_name": repo_info[2] if repo_info else None,
        "is_resource": prop_type == "resource",
        "is_ontology_linked": onto_source is not None,
        "ontology_source": onto_source,
        "is_literal": prop_type == "literal",
        "reproducibility_relevant": is_repro_relevant(pred_label)
    }


def get_property_category(prop: Dict) -> str:
    """Get the category of a property for balancing."""
    if prop["property_type"] == "url":
        return "url_repo" if prop["is_repo_url"] else "url_other"
    elif prop["property_type"] == "resource":
        return "resource_onto" if prop["is_ontology_linked"] else "resource_internal"
    else:
        return "literal"


def count_contribution_types(repro_props: List[Dict]) -> Dict[str, int]:
    """Count property types in a contribution."""
    counts = {"url_repo": 0, "url_other": 0, "resource_onto": 0, "resource_internal": 0, "literal": 0}
    for p in repro_props:
        cat = get_property_category(p)
        counts[cat] += 1
    return counts


def is_balanced(type_counts: Dict[str, int], min_per_type: int) -> bool:
    """Check if all types have minimum count."""
    return all(count >= min_per_type for count in type_counts.values())


def get_needed_types(type_counts: Dict[str, int], min_per_type: int) -> List[str]:
    """Get list of types that still need more samples."""
    return [t for t, c in type_counts.items() if c < min_per_type]


def contribution_helps_balance(contrib_types: Dict[str, int], type_counts: Dict[str, int], min_per_type: int) -> bool:
    """Check if this contribution helps achieve balance."""
    needed = get_needed_types(type_counts, min_per_type)
    # Accept if it has any type we still need
    for t in needed:
        if contrib_types.get(t, 0) > 0:
            return True
    return False


def collect_contributions(min_per_type: int = 40, max_contributions: int = 500) -> List[Dict]:
    """
    Collect contributions ensuring balanced distribution.
    
    Continues until we have at least min_per_type of each category:
    - url_repo, url_other, resource_onto, resource_internal, literal
    """
    contributions = []
    page = 0
    max_pages = 1000
    
    # Track property type distribution
    type_counts = {"url_repo": 0, "url_other": 0, "resource_onto": 0, "resource_internal": 0, "literal": 0}
    
    print(f"\n{'='*70}")
    print(f"COLLECTING BALANCED DATASET")
    print(f"{'='*70}")
    print(f"  Target: {min_per_type} minimum per type (20% each)")
    print(f"  Types: url_repo, url_other, resource_onto, resource_internal, literal")
    print(f"  Max contributions: {max_contributions}")
    print(f"{'='*70}")
    
    start_time = time.time()
    
    while not is_balanced(type_counts, min_per_type) and page < max_pages and len(contributions) < max_contributions:
        response = make_request(f"{ORKG_API_BASE}/papers?size=50&page={page}", is_papers=True)
        
        if not response:
            print(f"[ERROR] Failed page {page}")
            break
        
        papers = response.get("content", [])
        if not papers:
            print(f"[INFO] No more papers")
            break
        
        total_pages = response.get("page", {}).get("total_pages", "?")
        needed = get_needed_types(type_counts, min_per_type)
        
        print(f"\n[Page {page}/{total_pages}] Contributions: {len(contributions)} | "
              f"Still need: {needed}")
        print(f"  Current: repo:{type_counts['url_repo']} url:{type_counts['url_other']} "
              f"onto:{type_counts['resource_onto']} internal:{type_counts['resource_internal']} "
              f"lit:{type_counts['literal']}")
        
        for paper in papers:
            if is_balanced(type_counts, min_per_type) or len(contributions) >= max_contributions:
                break
            
            paper_id = paper.get("id")
            paper_title = paper.get("title", "Unknown")
            
            for contrib in paper.get("contributions", []):
                if is_balanced(type_counts, min_per_type) or len(contributions) >= max_contributions:
                    break
                
                contrib_id = contrib.get("id")
                
                # Get statements
                stmt_response = make_request(f"{ORKG_API_BASE}/statements/{contrib_id}/bundle")
                statements = stmt_response.get("statements", []) if stmt_response else []
                
                if not statements:
                    continue
                
                # Process properties
                all_props = [process_property(s) for s in statements]
                repro_props = [p for p in all_props if p["reproducibility_relevant"]]
                
                if not repro_props:
                    continue
                
                # Check if this contribution helps balance
                contrib_types = count_contribution_types(repro_props)
                
                # Always accept if we're not yet balanced and this helps
                if not is_balanced(type_counts, min_per_type):
                    if not contribution_helps_balance(contrib_types, type_counts, min_per_type):
                        # Skip if it doesn't help balance (unless we have very few contributions)
                        if len(contributions) > 50:
                            continue
                
                # Add contribution
                identifiers = paper.get("identifiers", {})
                paper_doi = identifiers.get("doi", [None])[0] if identifiers.get("doi") else None
                
                contributions.append({
                    "contribution_id": contrib_id,
                    "contribution_label": contrib.get("label", "Contribution"),
                    "paper_id": paper_id,
                    "paper_title": paper_title,
                    "paper_doi": paper_doi,
                    "all_properties": all_props,
                    "reproducibility_properties": repro_props,
                    "collected_at": datetime.now().isoformat()
                })
                
                # Update counts
                for cat, count in contrib_types.items():
                    type_counts[cat] += count
                
                # Log with what types this contribution added
                added = [f"{cat}:{count}" for cat, count in contrib_types.items() if count > 0]
                print(f"  ✓ {contrib_id} [{len(contributions)}] +{', '.join(added)}")
                
                time.sleep(0.05)
        
        page += 1
    
    elapsed = time.time() - start_time
    total_props = sum(type_counts.values())
    
    print(f"\n{'='*70}")
    print("COLLECTION COMPLETE")
    print(f"{'='*70}")
    print(f"  Time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"  Contributions: {len(contributions)}")
    print(f"  Balanced: {is_balanced(type_counts, min_per_type)}")
    print(f"\n  Property Distribution (target: {min_per_type} each, 20%):")
    for cat in ["url_repo", "url_other", "resource_onto", "resource_internal", "literal"]:
        count = type_counts[cat]
        pct = 100 * count / total_props if total_props > 0 else 0
        status = "✓" if count >= min_per_type else "✗"
        print(f"    {status} {cat:<20} {count:>4} ({pct:>5.1f}%)")
    print(f"    {'─'*35}")
    print(f"      {'TOTAL':<20} {total_props:>4} (100.0%)")
    
    if not is_balanced(type_counts, min_per_type):
        missing = [f"{cat} (have {type_counts[cat]}, need {min_per_type})" 
                   for cat in get_needed_types(type_counts, min_per_type)]
        print(f"\n  ⚠️  Could not find enough: {', '.join(missing)}")
        print(f"      This may be due to data scarcity in ORKG for these types.")
    
    return contributions


def save_contributions(contributions: List[Dict], output_file: str):
    """Save to JSON."""
    # Calculate stats
    type_counts = {"url_repo": 0, "url_other": 0, "resource_onto": 0, "resource_internal": 0, "literal": 0}
    repo_types = {}
    onto_sources = {}
    
    for c in contributions:
        for p in c.get("reproducibility_properties", []):
            cat = get_property_category(p)
            type_counts[cat] += 1
            
            if p.get("repo_type"):
                rt = p["repo_type"]
                repo_types[rt] = repo_types.get(rt, 0) + 1
            if p.get("ontology_source"):
                os = p["ontology_source"]
                onto_sources[os] = onto_sources.get(os, 0) + 1
    
    total = sum(type_counts.values())
    percentages = {k: round(100*v/total, 1) if total > 0 else 0 for k, v in type_counts.items()}
    
    output = {
        "metadata": {
            "collected_at": datetime.now().isoformat(),
            "total_contributions": len(contributions),
            "total_properties": total,
            "property_distribution": type_counts,
            "property_percentages": percentages,
            "repo_types": repo_types,
            "ontology_sources": onto_sources,
            "source": "ORKG API"
        },
        "contributions": contributions
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Saved to {output_file}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", "-o", default="orkg_contributions.json")
    parser.add_argument("--min-per-type", "-m", type=int, default=40,
                        help="Minimum properties per type (default: 20 = 20%% each)")
    parser.add_argument("--max-contributions", type=int, default=500,
                        help="Maximum contributions to collect")
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()
    
    print("=" * 70)
    print("ORKG BALANCED DATA COLLECTION")
    print("=" * 70)
    
    if not test_connection():
        return
    
    if args.test_only:
        return
    
    contributions = collect_contributions(
        min_per_type=args.min_per_type,
        max_contributions=args.max_contributions
    )
    if contributions:
        save_contributions(contributions, args.output)


if __name__ == "__main__":
    main()
