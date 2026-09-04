#!/usr/bin/env python3
"""
Bitsec-Striker: High-performance security analysis agent for Bitsec v2.

Inspired by Hound's multi-pass reasoning, stripped down to a single file
optimized for the Bitsec v2 sandbox and ScaBench metrics.

Architecture:
- FileManager: Efficient project traversal
- MiniGraph: Dict-based call graph (no networkx)
- ReasoningLoop: Two-pass Scout/Senior system
- InferenceClient: LLM communication via requests
"""

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import requests
from pydantic import BaseModel, Field


# ============================================================================
# Pydantic Schemas (Bitsec v2 Compatible)
# ============================================================================

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Vulnerability(BaseModel):
    """A security vulnerability finding."""
    title: str = Field(..., description="Vulnerability title")
    description: str = Field(..., description="Detailed description")
    vulnerability_type: str = Field(..., description="Type of vulnerability")
    severity: Severity = Field(..., description="Severity: critical, high, medium, low")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    location: str = Field(..., description="Location in code")
    file: str = Field(..., description="File path")
    id: str | None = Field(None, description="Unique ID")
    reported_by_model: str = Field("Bitsec-Striker", description="Model that reported this")
    status: str = Field("proposed", description="Status: proposed, confirmed, etc.")

    def __init__(self, **data):
        super().__init__(**data)
        if not self.id:
            id_source = f"{self.file}:{self.title}"
            self.id = hashlib.md5(id_source.encode()).hexdigest()[:16]


class ScoutFinding(BaseModel):
    """Scout pass finding - high-risk areas."""
    area: str = Field(..., description="High-risk area name")
    risk_type: str = Field(..., description="Type of risk: access_control, accounting, reentrancy, etc.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    functions: list[str] = Field(default_factory=list, description="Relevant function names")
    files: list[str] = Field(default_factory=list, description="Relevant file paths")
    reasoning: str = Field(..., description="Why this area is risky")

    class Config:
        extra = "forbid"


# ============================================================================
# FileManager: Efficient Project Traversal
# ============================================================================

class FileManager:
    """Manages file discovery and reading for security analysis."""
    
    IGNORED_DIRS = {
        'node_modules', '.git', '__pycache__', 'venv', 'env',
        'test', 'tests', 'spec', 'docs', 'build', 'dist',
        '.next', '.nuxt', 'target', 'bin', 'obj'
    }
    
    IGNORED_FILES = {
        '.gitignore', '.env', 'package-lock.json', 'yarn.lock',
        'README.md', 'LICENSE', 'CHANGELOG.md'
    }
    
    def __init__(self, project_dir: str | Path):
        self.project_dir = Path(project_dir)
        self.solidity_files: list[Path] = []
        self.file_cache: dict[Path, str] = {}
    
    def discover_files(self) -> list[Path]:
        """Discover all Solidity files, ignoring irrelevant directories."""
        self.solidity_files = []
        
        for root, dirs, files in os.walk(self.project_dir):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if d not in self.IGNORED_DIRS]
            
            for file in files:
                if file.endswith('.sol') and file not in self.IGNORED_FILES:
                    file_path = Path(root) / file
                    self.solidity_files.append(file_path)
        
        return self.solidity_files
    
    def read_file(self, file_path: Path) -> str:
        """Read file content with caching."""
        if file_path not in self.file_cache:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.file_cache[file_path] = f.read()
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                self.file_cache[file_path] = ""
        
        return self.file_cache[file_path]
    
    def get_file_lines(self, file_path: Path, start_line: int, end_line: int) -> str:
        """Get specific line range from a file."""
        content = self.read_file(file_path)
        lines = content.split('\n')
        
        # Adjust for 0-indexing
        start_idx = max(0, start_line - 1)
        end_idx = min(len(lines), end_line)
        
        return '\n'.join(lines[start_idx:end_idx])


# ============================================================================
# MiniGraph: Lightweight Dict-Based Call Graph
# ============================================================================

@dataclass
class ContractNode:
    """Represents a Solidity contract."""
    name: str
    file_path: str
    inherits_from: list[str] = field(default_factory=list)
    functions: dict[str, 'FunctionNode'] = field(default_factory=dict)
    state_vars: dict[str, str] = field(default_factory=dict)  # name -> type


@dataclass
class FunctionNode:
    """Represents a Solidity function."""
    name: str
    contract: str
    file_path: str
    visibility: str = "public"  # public, private, internal, external
    modifiers: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)  # Functions this calls
    state_writes: list[str] = field(default_factory=list)  # State variables written
    line_start: int = 0
    line_end: int = 0


class MiniGraph:
    """Lightweight call graph using Python dicts (no networkx)."""
    
    def __init__(self):
        self.contracts: dict[str, ContractNode] = {}
        self.function_map: dict[str, FunctionNode] = {}  # fully_qualified_name -> FunctionNode
        self.call_graph: dict[str, set[str]] = {}  # caller -> set of callees
    
    def add_contract(self, contract: ContractNode):
        """Add a contract to the graph."""
        self.contracts[contract.name] = contract
        
        # Index functions
        for func_name, func_node in contract.functions.items():
            full_name = f"{contract.name}.{func_name}"
            self.function_map[full_name] = func_node
            self.call_graph[full_name] = set(func_node.calls)
    
    def get_function(self, contract_name: str, func_name: str) -> FunctionNode | None:
        """Get a function by contract and name."""
        full_name = f"{contract_name}.{func_name}"
        return self.function_map.get(full_name)
    
    def get_callers(self, function_name: str) -> list[str]:
        """Get all functions that call this function."""
        callers = []
        for caller, callees in self.call_graph.items():
            if function_name in callees:
                callers.append(caller)
        return callers
    
    def get_callees(self, function_name: str) -> list[str]:
        """Get all functions called by this function."""
        return list(self.call_graph.get(function_name, set()))
    
    def find_public_state_writers(self) -> list[FunctionNode]:
        """Find public functions that write state without proper modifiers."""
        risky_funcs = []
        
        for func in self.function_map.values():
            if func.visibility in ['public', 'external']:
                # Check if it writes state
                if func.state_writes:
                    # Check if it has access control modifiers
                    has_access_control = any(
                        mod.lower() in ['onlyowner', 'onlyadmin', 'onlyrole', 'auth']
                        for mod in func.modifiers
                    )
                    if not has_access_control:
                        risky_funcs.append(func)
        
        return risky_funcs
    
    def find_reentrancy_candidates(self) -> list[FunctionNode]:
        """Find functions that make external calls after state changes."""
        candidates = []
        
        for func in self.function_map.values():
            if func.state_writes:
                # Check if it makes external calls
                for call in func.calls:
                    if call.startswith('call') or call.startswith('send') or call.startswith('transfer'):
                        candidates.append(func)
                        break
        
        return candidates


# ============================================================================
# Solidity Parser (Regex-based, lightweight)
# ============================================================================

class SolidityParser:
    """Lightweight Solidity parser using regex."""
    
    # Regex patterns
    CONTRACT_PATTERN = re.compile(
        r'contract\s+(\w+)\s*(?:is\s+([\w,\s]+))?\s*\{',
        re.MULTILINE
    )
    FUNCTION_PATTERN = re.compile(
        r'(?:function\s+)?(\w+)\s*\(([^)]*)\)\s*(public|private|internal|external)?\s*(?:view|pure|payable)?\s*(?:returns\s*\([^)]*\))?\s*(?:modifier\s+(\w+))?',
        re.MULTILINE
    )
    MODIFIER_PATTERN = re.compile(r'modifier\s+(\w+)')
    STATE_VAR_PATTERN = re.compile(
        r'(?:mapping\s*\([^)]+\)\s+)?(\w+(?:\[\])?)\s+(?:public|private|internal|constant)?\s*(\w+);',
        re.MULTILINE
    )
    CALL_PATTERN = re.compile(
        r'\b(\w+)\.(?:call|delegatecall|staticcall|send|transfer)\s*\('
    )
    EXTERNAL_CALL_PATTERN = re.compile(
        r'\b(\w+)\s*\.\s*(\w+)\s*\('
    )
    
    def __init__(self, file_manager: FileManager):
        self.file_manager = file_manager
    
    def parse_file(self, file_path: Path) -> list[ContractNode]:
        """Parse a Solidity file and extract contracts."""
        content = self.file_manager.read_file(file_path)
        contracts = []
        
        # Find all contracts
        for match in self.CONTRACT_PATTERN.finditer(content):
            contract_name = match.group(1)
            inheritance_str = match.group(2) or ""
            inherits = [i.strip() for i in inheritance_str.split(',') if i.strip()]
            
            contract = ContractNode(
                name=contract_name,
                file_path=str(file_path),
                inherits_from=inherits
            )
            
            # Parse functions within this contract
            self._parse_contract_functions(content, match.start(), contract)
            
            # Parse state variables
            self._parse_state_vars(content, match.start(), contract)
            
            contracts.append(contract)
        
        return contracts
    
    def _parse_contract_functions(self, content: str, start_pos: int, contract: ContractNode):
        """Parse functions within a contract."""
        # Find contract body
        brace_count = 0
        in_contract = False
        contract_start = start_pos
        contract_end = len(content)  # Default to end of file
        
        for i, char in enumerate(content[start_pos:], start=start_pos):
            if char == '{':
                brace_count += 1
                in_contract = True
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    contract_end = i
                    break
        
        if not in_contract:
            return
        
        contract_body = content[contract_start:contract_end]
        
        # Find functions
        for match in self.FUNCTION_PATTERN.finditer(contract_body):
            func_name = match.group(1)
            visibility = match.group(3) or "public"
            modifier = match.group(4)
            
            # Calculate line numbers
            abs_pos = contract_start + match.start()
            line_start = content[:abs_pos].count('\n') + 1
            
            func_node = FunctionNode(
                name=func_name,
                contract=contract.name,
                file_path=contract.file_path,
                visibility=visibility,
                modifiers=[modifier] if modifier else [],
                line_start=line_start
            )
            
            # Find function calls within this function
            self._parse_function_calls(contract_body, match.start(), match.end(), func_node)
            
            # Find state writes
            self._parse_state_writes(contract_body, match.start(), match.end(), func_node)
            
            contract.functions[func_name] = func_node
    
    def _parse_function_calls(self, content: str, start: int, end: int, func: FunctionNode):
        """Parse function calls within a function."""
        func_body = content[start:end]
        
        # Find external calls
        for match in self.EXTERNAL_CALL_PATTERN.finditer(func_body):
            target = match.group(1)
            method = match.group(2)
            func.calls.append(f"{target}.{method}")
        
        # Find low-level calls
        for match in self.CALL_PATTERN.finditer(func_body):
            func.calls.append(match.group(0))
    
    def _parse_state_writes(self, content: str, start: int, end: int, func: FunctionNode):
        """Parse state variable writes within a function."""
        func_body = content[start:end]
        
        # Look for assignment patterns
        assignment_pattern = re.compile(r'(\w+)\s*=')
        for match in assignment_pattern.finditer(func_body):
            var_name = match.group(1)
            # Filter out local variables (simplified heuristic)
            if var_name[0].isupper() or var_name.startswith('_'):
                func.state_writes.append(var_name)
    
    def _parse_state_vars(self, content: str, start_pos: int, contract: ContractNode):
        """Parse state variables within a contract."""
        # Find contract body
        brace_count = 0
        in_contract = False
        contract_start = start_pos
        contract_end = len(content)  # Default to end of file
        
        for i, char in enumerate(content[start_pos:], start=start_pos):
            if char == '{':
                brace_count += 1
                in_contract = True
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    contract_end = i
                    break
        
        if not in_contract:
            return
        
        contract_body = content[contract_start:contract_end]
        
        # Find state variables
        for match in self.STATE_VAR_PATTERN.finditer(contract_body):
            var_type = match.group(1)
            var_name = match.group(2)
            contract.state_vars[var_name] = var_type


# ============================================================================
# InferenceClient: LLM Communication
# ============================================================================

class InferenceClient:
    """Client for communicating with LLM inference API."""
    
    def __init__(self, api_url: str, api_key: str | None = None):
        self.api_url = api_url
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    def call_llm(self, prompt: str, system_prompt: str = "", temperature: float = 0.7) -> str:
        """Call the LLM with a prompt."""
        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": 4096
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            print(f"LLM call failed: {e}")
            return ""
    
    def call_llm_structured(self, prompt: str, schema: type[BaseModel], system_prompt: str = "") -> BaseModel | None:
        """Call LLM with structured output."""
        # Add schema to prompt
        schema_desc = json.dumps(schema.model_json_schema(), indent=2)
        full_prompt = f"""
You must respond with valid JSON matching this schema:
{schema_desc}

{prompt}
"""
        
        response = self.call_llm(full_prompt, system_prompt, temperature=0.3)
        
        # Extract JSON from response
        try:
            # Try to find JSON in response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                return schema(**data)
        except Exception as e:
            print(f"Failed to parse structured response: {e}")
        
        return None


# ============================================================================
# ReasoningLoop: Two-Pass Scout/Senior System
# ============================================================================

class ReasoningLoop:
    """Two-pass reasoning system: Scout (exploration) + Senior (verification)."""
    
    SCOUT_SYSTEM_PROMPT = """You are a security Scout agent. Your job is to quickly scan Solidity code and identify high-risk areas.

Focus on:
1. Access Control: Public functions without proper modifiers
2. Accounting: Functions that update balances/rewards
3. Reentrancy: External calls after state changes
4. Upgradeability: Critical admin functions
5. Asset Transfers: Functions moving tokens/ETH

For each high-risk area, provide:
- area: Name of the risky area
- risk_type: Category of risk
- confidence: 0.0-1.0 score
- functions: List of relevant function names
- files: List of relevant file paths
- reasoning: Why this is risky

Be thorough but fast. Identify 5-10 highest-risk areas."""

    SENIOR_SYSTEM_PROMPT = """You are a security Senior agent. Your job is to deeply analyze specific high-risk areas and confirm vulnerabilities.

For each area, you must:
1. Extract the exact code for all relevant functions
2. Trace the call graph to understand the full flow
3. Identify the specific vulnerability
4. Provide a detailed explanation
5. Suggest a fix

You must respond with a valid Vulnerability object containing:
- title: Clear vulnerability title
- severity: critical/high/medium/low
- description: Detailed explanation of the vulnerability
- affected_files: List of file paths
- code_snippets: Relevant code snippets
- recommendation: How to fix it

Be precise and evidence-based. Only report confirmed vulnerabilities."""

    def __init__(self, graph: MiniGraph, file_manager: FileManager, inference_client: InferenceClient):
        self.graph = graph
        self.file_manager = file_manager
        self.inference = inference_client
        self.findings: list[Vulnerability] = []
        self.seen_hashes: set[str] = set()
    
    def run_scout_pass(self) -> list[ScoutFinding]:
        """Pass 1: Scout - identify high-risk areas."""
        print("[SCOUT] Running Scout pass...")
        
        # Build context for Scout
        context = self._build_scout_context()
        
        prompt = f"""
Analyze this Solidity codebase and identify high-risk security areas.

{context}

Return your findings as a JSON array of ScoutFinding objects.
"""
        
        response = self.inference.call_llm(prompt, self.SCOUT_SYSTEM_PROMPT)
        
        # Parse Scout findings
        findings = []
        try:
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                findings = [ScoutFinding(**item) for item in data]
        except Exception as e:
            print(f"Failed to parse Scout findings: {e}")
        
        print(f"[SCOUT] Scout found {len(findings)} high-risk areas")
        return findings

    def run_senior_pass(self, scout_findings: list[ScoutFinding]) -> list[Vulnerability]:
        """Pass 2: Senior - verify and detail vulnerabilities."""
        print("[SENIOR] Running Senior pass...")
        
        vulnerabilities = []
        
        for finding in scout_findings:
            print(f"  Analyzing: {finding.area}")
            
            # Build detailed context for this finding
            context = self._build_senior_context(finding)
            
            prompt = f"""
Analyze this high-risk area in detail and confirm if there's a vulnerability.

{context}

Return your analysis as a single Vulnerability object. If no vulnerability exists, return null.
"""
            
            response = self.inference.call_llm(prompt, self.SENIOR_SYSTEM_PROMPT)
            
            # Parse vulnerability
            try:
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    data = json.loads(json_str)
                    
                    # Check if it's a valid vulnerability (not null)
                    if data and 'title' in data:
                        vuln = Vulnerability(**data)
                        
                        # Deduplicate
                        vuln_hash = self._hash_vulnerability(vuln)
                        if vuln_hash not in self.seen_hashes:
                            self.seen_hashes.add(vuln_hash)
                            vulnerabilities.append(vuln)
                            print(f"    [OK] Confirmed: {vuln.title}")
                        else:
                            print(f"    [SKIP] Duplicate, skipping")
            except Exception as e:
                print(f"    [ERROR] Failed to parse: {e}")

        print(f"[SENIOR] Senior confirmed {len(vulnerabilities)} vulnerabilities")
        return vulnerabilities
    
    def _build_scout_context(self) -> str:
        """Build context for Scout pass."""
        context_parts = []
        
        # List all contracts
        context_parts.append("## Contracts")
        for contract_name, contract in self.graph.contracts.items():
            context_parts.append(f"\n### {contract_name}")
            context_parts.append(f"File: {contract.file_path}")
            context_parts.append(f"Inherits: {', '.join(contract.inherits_from)}")
            
            # List functions
            context_parts.append("\nFunctions:")
            for func_name, func in contract.functions.items():
                context_parts.append(f"  - {func_name} ({func.visibility})")
                if func.modifiers:
                    context_parts.append(f"    Modifiers: {', '.join(func.modifiers)}")
        
        # Highlight risky patterns
        context_parts.append("\n## Risky Patterns Detected")
        
        risky_funcs = self.graph.find_public_state_writers()
        if risky_funcs:
            context_parts.append("\nPublic functions writing state without access control:")
            for func in risky_funcs[:10]:  # Limit to 10
                context_parts.append(f"  - {func.contract}.{func.name}")
        
        reentrancy_candidates = self.graph.find_reentrancy_candidates()
        if reentrancy_candidates:
            context_parts.append("\nPotential reentrancy candidates:")
            for func in reentrancy_candidates[:10]:
                context_parts.append(f"  - {func.contract}.{func.name}")
        
        return "\n".join(context_parts)
    
    def _build_senior_context(self, finding: ScoutFinding) -> str:
        """Build detailed context for Senior pass."""
        context_parts = []
        
        context_parts.append(f"## High-Risk Area: {finding.area}")
        context_parts.append(f"Risk Type: {finding.risk_type}")
        context_parts.append(f"Confidence: {finding.confidence}")
        context_parts.append(f"Reasoning: {finding.reasoning}")
        
        # Extract code for relevant functions
        context_parts.append("\n## Relevant Code")
        
        for func_name in finding.functions:
            # Find the function
            for func in self.graph.function_map.values():
                if func.name == func_name or func_name in func.name:
                    context_parts.append(f"\n### {func.contract}.{func.name}")
                    context_parts.append(f"Visibility: {func.visibility}")
                    context_parts.append(f"Modifiers: {', '.join(func.modifiers)}")
                    context_parts.append(f"Calls: {', '.join(func.calls)}")
                    context_parts.append(f"State writes: {', '.join(func.state_writes)}")
                    
                    # Get actual code
                    file_path = Path(func.file_path)
                    code = self.file_manager.get_file_lines(
                        file_path,
                        func.line_start,
                        func.line_start + 50  # Get 50 lines
                    )
                    context_parts.append(f"\n```solidity\n{code}\n```")
        
        # Show call graph context
        context_parts.append("\n## Call Graph Context")
        for func_name in finding.functions:
            callers = self.graph.get_callers(func_name)
            callees = self.graph.get_callees(func_name)
            
            context_parts.append(f"\n### {func_name}")
            if callers:
                context_parts.append(f"Called by: {', '.join(callers)}")
            if callees:
                context_parts.append(f"Calls: {', '.join(callees)}")
        
        return "\n".join(context_parts)
    
    def _hash_vulnerability(self, vuln: Vulnerability) -> str:
        """Create MD5 hash for deduplication."""
        content = f"{vuln.title}|{vuln.severity}|{vuln.description[:200]}"
        return hashlib.md5(content.encode()).hexdigest()


# ============================================================================
# BitsecStriker: Main Agent Class
# ============================================================================

class BitsecStriker:
    """Main Bitsec-Striker agent class for test compatibility."""
    
    def __init__(self, project_dir: str, model: str, api_url: str, api_token: str):
        """
        Initialize the agent.
        
        Args:
            project_dir: Path to project directory
            model: Model name (not used in current implementation)
            api_url: Inference API URL
            api_token: API token
        """
        self.project_dir = project_dir
        self.api_url = api_url
        self.api_token = api_token
        
    def analyze(self, max_findings: int = 10) -> list[Vulnerability]:
        """
        Analyze the project and return vulnerabilities.
        
        Args:
            max_findings: Maximum number of findings to return
            
        Returns:
            List of Vulnerability objects
        """
        # Call the existing agent_main function
        results = agent_main(self.project_dir, self.api_url)
        
        # Convert dict results to Vulnerability objects
        vulnerabilities = []
        for result in results[:max_findings]:
            # Map the dictionary fields to Vulnerability object
            vuln = Vulnerability(
                title=result.get('title', 'Unknown'),
                description=result.get('description', ''),
                vulnerability_type=result.get('vulnerability_type', ''),
                severity=Severity(result.get('severity', 'low')),
                confidence=float(result.get('confidence', 0.5)),
                location=result.get('location', ''),
                file=result.get('file', ''),
                id=result.get('id', None),
                reported_by_model=result.get('reported_by_model', 'Bitsec-Striker'),
                status=result.get('status', 'proposed')
            )
            vulnerabilities.append(vuln)
        
        return vulnerabilities


# ============================================================================
# Main Agent Entry Point
# ============================================================================

def agent_main(project_dir: str, inference_api: str) -> list[dict]:
    """
    Main entry point for Bitsec-Striker agent.

    Args:
        project_dir: Path to the project directory to analyze
        inference_api: URL for the inference API

    Returns:
        List of vulnerability dictionaries
    """
    print("[START] Bitsec-Striker Agent Starting...")
    print(f"[INFO] Project: {project_dir}")
    print(f"[INFO] Inference API: {inference_api}")

    # Initialize components
    file_manager = FileManager(project_dir)
    parser = SolidityParser(file_manager)
    graph = MiniGraph()
    inference_client = InferenceClient(inference_api)
    reasoning_loop = ReasoningLoop(graph, file_manager, inference_client)

    # Phase 1: Discover files
    print("\n[PHASE 1] Discovering files...")
    solidity_files = file_manager.discover_files()
    print(f"   Found {len(solidity_files)} Solidity files")

    # Phase 2: Build graph
    print("\n[PHASE 2] Building call graph...")
    for file_path in solidity_files:
        contracts = parser.parse_file(file_path)
        for contract in contracts:
            graph.add_contract(contract)

    print(f"   Parsed {len(graph.contracts)} contracts")
    print(f"   Indexed {len(graph.function_map)} functions")

    # Phase 3: Scout pass
    print("\n[PHASE 3] Scout pass (exploration)...")
    scout_findings = reasoning_loop.run_scout_pass()

    # Phase 4: Senior pass
    print("\n[PHASE 4] Senior pass (verification)...")
    vulnerabilities = reasoning_loop.run_senior_pass(scout_findings)

    # Convert to dict format for Bitsec
    results = [vuln.model_dump() for vuln in vulnerabilities]

    print(f"\n[DONE] Analysis complete!")
    print(f"   Found {len(results)} confirmed vulnerabilities")

    return results


# ============================================================================
# CLI Entry Point
# ============================================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python agent.py <project_dir> <inference_api>")
        sys.exit(1)
    
    project_dir = sys.argv[1]
    inference_api = sys.argv[2]
    
    results = agent_main(project_dir, inference_api)
    
    # Output results
    print("\n" + "="*80)
    print("VULNERABILITIES FOUND:")
    print("="*80)
    
    for i, vuln in enumerate(results, 1):
        print(f"\n{i}. {vuln['title']}")
        print(f"   Severity: {vuln['severity']}")
        print(f"   Files: {', '.join(vuln['affected_files'])}")
        print(f"   Description: {vuln['description'][:200]}...")
    
    # Save to JSON
    output_file = "vulnerabilities.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n[SAVED] Results saved to {output_file}")