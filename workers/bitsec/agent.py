"""Bitsec Agent using OpenCode Go API (mimo-v2.5)

Standalone version - no bittensor SDK dependency.
Returns PredictionResponse with structured vulnerability objects.
"""
import json
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

sys.path.insert(0, str(Path("/root/bitt")))
sys.path.insert(0, str(Path("/root/bitt/workers/bitsec")))

from opencode_harness import call_model


class VulnerabilitySeverity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class VulnerabilityCategory(str, Enum):
    REENTRANCY = "REENTRANCY"
    ACCESS_CONTROL = "ACCESS_CONTROL"
    ARITHMETIC = "ARITHMETIC"
    LOGIC = "LOGIC"
    EXTERNAL_CALL = "EXTERNAL_CALL"
    UPGRADEABLE = "UPGRADEABLE"
    GOVERNANCE = "GOVERNANCE"
    OTHER = "OTHER"


@dataclass
class LineRange:
    start: int
    end: int


@dataclass
class Vulnerability:
    title: str
    severity: VulnerabilitySeverity
    category: VulnerabilityCategory
    description: str
    vulnerable_code: str
    code_to_exploit: str
    rewritten_code_to_fix_vulnerability: str
    line_ranges: Optional[List[LineRange]] = None


@dataclass
class PredictionResponse:
    prediction: bool
    vulnerabilities: List[Vulnerability] = field(default_factory=list)


def analyze_code(code: str) -> PredictionResponse:
    """Analyze code for vulnerabilities using OpenCode Go API."""
    
    prompt = f"""Analyze this Solidity code for security vulnerabilities.

### Code:
{code}

### Return JSON with this exact structure:
{{
    "prediction": true/false,
    "vulnerabilities": [
        {{
            "title": "short title",
            "severity": "CRITICAL/HIGH/MEDIUM/LOW",
            "category": "REENTRANCY/ACCESS_CONTROL/ARITHMETIC/LOGIC/EXTERNAL_CALL/UPGRADEABLE/GOVERNANCE/OTHER",
            "description": "detailed description of the vulnerability",
            "vulnerable_code": "the vulnerable code snippet",
            "code_to_exploit": "code that exploits the vulnerability",
            "rewritten_code_to_fix_vulnerability": "fixed code snippet",
            "line_ranges": [{{"start": 10, "end": 15}}]
        }}
    ]
}}

Return ONLY valid JSON. Be specific about line numbers and code snippets."""

    result = call_model("mimo-v2.5", prompt, max_tokens=4000)
    content = result.get('content', '')
    
    try:
        # Parse JSON response
        clean = content.strip()
        if clean.startswith('```'):
            first_nl = clean.find('\n')
            if first_nl > 0:
                clean = clean[first_nl + 1:]
            if clean.rstrip().endswith('```'):
                clean = clean.rstrip()[:-3].rstrip()
        
        start = clean.find('{')
        end = clean.rfind('}') + 1
        if start >= 0 and end > start:
            data = json.loads(clean[start:end])
            
            # Convert to PredictionResponse
            vulnerabilities = []
            for v in data.get('vulnerabilities', []):
                # Map category string to VulnerabilityCategory
                category_map = {
                    "REENTRANCY": VulnerabilityCategory.REENTRANCY,
                    "ACCESS_CONTROL": VulnerabilityCategory.ACCESS_CONTROL,
                    "ARITHMETIC": VulnerabilityCategory.ARITHMETIC,
                    "LOGIC": VulnerabilityCategory.LOGIC,
                    "EXTERNAL_CALL": VulnerabilityCategory.EXTERNAL_CALL,
                    "UPGRADEABLE": VulnerabilityCategory.UPGRADEABLE,
                    "GOVERNANCE": VulnerabilityCategory.GOVERNANCE,
                    "OTHER": VulnerabilityCategory.OTHER,
                }
                
                # Map severity string to VulnerabilitySeverity
                severity_map = {
                    "CRITICAL": VulnerabilitySeverity.CRITICAL,
                    "HIGH": VulnerabilitySeverity.HIGH,
                    "MEDIUM": VulnerabilitySeverity.MEDIUM,
                    "LOW": VulnerabilitySeverity.LOW,
                }
                
                # Parse line ranges
                line_ranges = []
                for lr in v.get('line_ranges', []):
                    if isinstance(lr, dict):
                        line_ranges.append(LineRange(start=lr.get('start', 0), end=lr.get('end', 0)))
                
                vuln = Vulnerability(
                    title=v.get('title', 'Unknown vulnerability'),
                    severity=severity_map.get(v.get('severity', 'MEDIUM'), VulnerabilitySeverity.MEDIUM),
                    category=category_map.get(v.get('category', 'OTHER'), VulnerabilityCategory.OTHER),
                    description=v.get('description', ''),
                    vulnerable_code=v.get('vulnerable_code', ''),
                    code_to_exploit=v.get('code_to_exploit', ''),
                    rewritten_code_to_fix_vulnerability=v.get('rewritten_code_to_fix_vulnerability', ''),
                    line_ranges=line_ranges if line_ranges else None,
                )
                vulnerabilities.append(vuln)
            
            return PredictionResponse(
                prediction=data.get('prediction', len(vulnerabilities) > 0),
                vulnerabilities=vulnerabilities,
            )
    
    except Exception as e:
        print(f"Error parsing response: {e}")
    
    # Return empty response on failure
    return PredictionResponse(prediction=False, vulnerabilities=[])


def predict(code: str) -> PredictionResponse:
    """Main prediction function."""
    return analyze_code(code)


if __name__ == "__main__":
    # Test with sample code
    test_code = """
pragma solidity ^0.8.0;

contract Vulnerable {
    mapping(address => uint256) public balances;
    
    function withdraw(uint256 amount) public {
        require(balances[msg.sender] >= amount);
        (bool success, ) = msg.sender.call{value: amount}("");
        require(success);
        balances[msg.sender] -= amount;
    }
}
"""
    result = predict(test_code)
    print(f"Prediction: {result.prediction}")
    print(f"Vulnerabilities: {len(result.vulnerabilities)}")
    for v in result.vulnerabilities:
        print(f"  - {v.title} ({v.severity})")
        print(f"    Category: {v.category}")
        print(f"    Description: {v.description[:100]}...")
