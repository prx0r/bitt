"""Test mw-audit-v1 on Superposition benchmark."""
import sys, json, time
from pathlib import Path

sys.path.insert(0, str(Path('/root/bitt')))
sys.path.insert(0, str(Path('/root/bitt/mining/sn60/candidates/mw-audit-v1')))

from agent import MWAgent, Vulnerability, Severity


def load_ground_truth(project_id: str) -> list:
    """Load ground truth from ScaBench dataset."""
    dataset_path = Path('/root/bitt/subnets/sn60-bitsec/tools/scabench/datasets/curated-2025-08-18/curated-2025-08-18.json')
    dataset = json.loads(dataset_path.read_text())
    proj = next((p for p in dataset if p['project_id'] == project_id), None)
    if proj:
        return proj.get('vulnerabilities', [])
    return []


def score_findings(findings: list, ground_truth: list) -> dict:
    """Score findings against ground truth."""
    tp = 0
    matched_gt = set()
    
    for f in findings:
        f_title = f.get('title', '').lower()
        for j, gt in enumerate(ground_truth):
            if j in matched_gt:
                continue
            gt_title = gt.get('title', '').lower()
            f_words = set(f_title.split())
            gt_words = set(gt_title.split())
            if f_words and gt_words:
                overlap = len(f_words & gt_words) / max(len(f_words | gt_words), 1)
                if overlap >= 0.15:
                    matched_gt.add(j)
                    tp += 1
                    break
    
    fn = len(ground_truth) - len(matched_gt)
    fp = len(findings) - tp
    dr = tp / max(len(ground_truth), 1)
    precision = tp / max(tp + fp, 1)
    f1 = 2 * precision * dr / max(precision + dr, 0.001)
    
    # Check if all high/critical found
    high_crit = [gt for gt in ground_truth if gt.get('severity') in ['high', 'critical']]
    high_crit_matched = sum(1 for j in matched_gt if ground_truth[j].get('severity') in ['high', 'critical'])
    all_found = high_crit_matched == len(high_crit)
    
    return {
        'tp': tp,
        'fp': fp,
        'fn': fn,
        'dr': dr,
        'precision': precision,
        'f1': f1,
        'all_high_crit_found': all_found,
        'high_crit_expected': len(high_crit),
        'high_crit_found': high_crit_matched,
    }


def test_project(project_id: str, n_runs: int = 3):
    """Test on a single project."""
    print(f'\n=== {project_id} ===')
    
    # Load ground truth
    ground_truth = load_ground_truth(project_id)
    print(f'Ground truth: {len(ground_truth)} vulns')
    
    # Run agent n times
    results = []
    for run_i in range(n_runs):
        print(f'\nRun {run_i + 1}/{n_runs}:')
        
        agent = MWAgent(inference_api='http://bitsec_proxy:8000')
        source_dir = Path(f'/root/bitt/data/scabench-repos/{project_id}')
        
        if not source_dir.exists():
            print(f'  Project not found: {source_dir}')
            continue
        
        try:
            result = agent.analyze_project(source_dir, project_id)
            findings = [v.model_dump() for v in result.vulnerabilities]
            
            scores = score_findings(findings, ground_truth)
            results.append(scores)
            
            print(f'  Found: {len(findings)} vulns')
            print(f'  High/Crit found: {scores["high_crit_found"]}/{scores["high_crit_expected"]}')
            print(f'  All found: {scores["all_high_crit_found"]}')
        except Exception as e:
            print(f'  Error: {e}')
    
    # Aggregate
    if results:
        all_found_count = sum(1 for r in results if r['all_high_crit_found'])
        project_pass = all_found_count >= 2  # 2/3 runs must find all
        
        print(f'\nSummary:')
        print(f'  Runs: {len(results)}')
        print(f'  All high/crit found in: {all_found_count}/{len(results)} runs')
        print(f'  Project PASS: {project_pass}')
    
    return results


def main():
    """Test on all benchmark projects."""
    projects = [
        'code4rena_superposition_2025_01',
        'code4rena_lambowin_2025_02',
        'code4rena_loopfi_2025_02',
        'code4rena_secondswap_2025_02',
    ]
    
    print('=== MW-AUDIT-V1 BENCHMARK TEST ===')
    
    all_results = {}
    for project_id in projects:
        results = test_project(project_id, n_runs=3)
        all_results[project_id] = results
    
    # Overall summary
    print('\n' + '='*60)
    print('OVERALL SUMMARY')
    print('='*60)
    
    total_projects = len(all_results)
    passed_projects = 0
    
    for project_id, results in all_results.items():
        if results:
            all_found_count = sum(1 for r in results if r['all_high_crit_found'])
            project_pass = all_found_count >= 2
            if project_pass:
                passed_projects += 1
            print(f'{project_id}: {"PASS" if project_pass else "FAIL"} ({all_found_count}/{len(results)} runs)')
    
    print(f'\nProjects passed: {passed_projects}/{total_projects}')
    print(f'Validator score: {passed_projects/total_projects:.1%}')


if __name__ == "__main__":
    main()
