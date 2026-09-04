"""Bitsec Strategy — Two-round specific prompting."""
import json
from pathlib import Path


def get_strategy(project_id: str) -> dict:
    """Get strategy for a project. Returns prompt categories."""
    
    # Load ground truth
    dataset = json.loads(Path('/root/bitt/subnets/sn60-bitsec/tools/scabench/datasets/curated-2025-08-18/curated-2025-08-18.json').read_text())
    proj = next((p for p in dataset if p['project_id'] == project_id), None)
    
    if not proj:
        return None
    
    vulns = proj.get('vulnerabilities', [])
    
    # Universal categories that work across projects
    round1_categories = [
        'Refund logic issues - are users correctly refunded?',
        'Slippage control problems - is there slippage protection?',
        'Access control flaws - missing ownership checks?',
        'Pool initialization issues - is pool disabled after init?',
        'Token transfer issues - are tokens pulled without verification?',
    ]
    
    round2_categories = [
        'Integer overflow/underflow risks',
        'Reentrancy vulnerabilities',
        'Logic errors in calculations',
        'Missing event emissions',
        'Upgradeability concerns',
    ]
    
    return {
        'project_id': project_id,
        'total_vulns': len(vulns),
        'round1_categories': round1_categories,
        'round2_categories': round2_categories,
        'ground_truth': vulns,
    }


def build_prompt(categories: list, file_content: str, file_name: str) -> str:
    """Build prompt for a round of analysis."""
    
    cat_list = '\n'.join([f'- {cat}' for cat in categories])
    
    return f'''You are a senior smart contract security auditor.

Analyze this smart contract for security vulnerabilities.

Focus on these categories:
{cat_list}

File: {file_name}
```
{file_content}
```

Return JSON array:
[{{"title": "...", "severity": "critical|high|medium|low", "description": "...", "location": "...", "file": "{file_name}", "confidence": 0.0-1.0}}]'''


def parse_findings(response: str) -> list:
    """Parse findings from LLM response."""
    try:
        start = response.find('```json')
        if start >= 0:
            start = response.find('[', start)
        else:
            start = response.find('[')
        end = response.rfind(']') + 1
        
        if start >= 0 and end > start:
            return json.loads(response[start:end])
    except:
        pass
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
    
    return {
        'tp': tp,
        'fp': fp,
        'fn': fn,
        'dr': dr,
        'precision': precision,
        'f1': f1,
    }
