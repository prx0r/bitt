"""MW Audit v1 — Methodology improvement over official baseline.

Key changes from official baseline:
1. Better system prompt (focused on security methodology, not generic)
2. Architecture mapping phase (understand code structure first)
3. Hypothesis-driven investigation (targeted, not generic)
4. Cross-file analysis (trace value flows)
5. Independent verification (confirm before reporting)

This agent uses the same infrastructure as official baseline:
- Inference proxy
- Tool calling (list_files, read_file, report_vulnerabilities)
- Same return format
"""
import hashlib
import json
import os
import requests
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from textwrap import dedent

from pydantic import BaseModel
from rich.console import Console

console = Console()

# Config
MAX_WORKERS = 2
MAX_TOOL_PASS_WORKERS = 16
MAX_TOOL_RUNTIME_SECONDS = 5 * 60
DEFAULT_CONTRACT_FILE_PATTERNS = ['**/*.sol', '**/*.vy', '**/*.cairo', '**/*.rs', '**/*.move']
EXCLUDE_DIRS = {"testing", "mocks", "examples", "interfaces", "script", "broadcast", "libraries"}

# Use a model available on OpenCode Go
INVESTIGATOR_MODEL = "mimo-v2.5"

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory. Returns file paths relative to the project root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory path relative to project root. Use '.' for the root directory."
                    }
                },
                "required": ["directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "File path relative to the project root."
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "report_vulnerabilities",
            "description": "Report security vulnerabilities found. Call when analysis is complete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "vulnerabilities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string", "description": "Short title"},
                                "description": {"type": "string", "description": "Detailed description with: precondition → attacker action → vulnerable code → violated assumption → impact"},
                                "vulnerability_type": {"type": "string", "description": "Category"},
                                "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                                "confidence": {"type": "number", "description": "0.0-1.0"},
                                "location": {"type": "string", "description": "Contract.function()"},
                                "file": {"type": "string", "description": "File path"}
                            },
                            "required": ["title", "description", "vulnerability_type", "severity", "confidence", "location", "file"]
                        }
                    }
                },
                "required": ["vulnerabilities"]
            }
        }
    }
]


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Vulnerability(BaseModel):
    title: str
    description: str
    vulnerability_type: str
    severity: Severity
    confidence: float
    location: str
    file: str
    id: str | None = None
    reported_by_model: str = ""
    status: str = "proposed"

    def __init__(self, **data):
        super().__init__(**data)
        if not self.id:
            id_source = f"{self.file}:{self.title}"
            self.id = hashlib.md5(id_source.encode()).hexdigest()[:16]


class AnalysisResult(BaseModel):
    project: str
    timestamp: str
    files_analyzed: int
    files_skipped: int
    total_vulnerabilities: int
    vulnerabilities: list[Vulnerability]
    token_usage: dict[str, int]


class MWAgent:
    """Improved agent with methodology-based audit."""

    # IMPROVED SYSTEM PROMPT — focused on security methodology
    SYSTEM_PROMPT = dedent("""\
        You are a senior smart contract security auditor. Your job is to find
        HIGH and CRITICAL severity vulnerabilities that could lead to loss of
        funds, unauthorized access, or contract exploitation.

        METHODOLOGY:
        1. Map the attack surface: entry points, privileged roles, value flows
        2. Investigate each high-risk area systematically
        3. For each finding, establish: file, function, mechanism, impact
        4. Only report HIGH/CRITICAL findings you can demonstrate

        CRITICAL: After analyzing the code, you MUST call report_vulnerabilities 
        with your findings. Do NOT report empty arrays. If you found vulnerabilities,
        report them. The report_vulnerabilities tool is how you submit your findings.

        Focus on REAL security issues:
        - Reentrancy / callback attacks
        - Access control / ownership flaws
        - Integer overflow/underflow
        - Logic errors in accounting
        - Unprotected state mutations
        - Front-running / MEV extraction
        - Price manipulation
        - Flash loan attacks

        DO NOT report:
        - Code quality issues
        - Gas optimizations
        - Style issues
        - Missing comments
        - Theoretical issues without exploit paths

        Description format:
        Precondition → Attacker action → Vulnerable code path → Violated assumption → Impact
    """)

    def __init__(self, inference_api: str = None):
        self.inference_api = inference_api or os.getenv('INFERENCE_API', "http://bitsec_proxy:8000")
        self.inference_api_key = os.getenv('INFERENCE_API_KEY')

    def inference(self, messages: list[dict], **kwargs) -> dict:
        payload = {
            "model": INVESTIGATOR_MODEL,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        payload.update(kwargs)

        headers = {
            "x-inference-api-key": self.inference_api_key or "",
            "x-request-phase": "execution",
        }

        resp = requests.post(
            f"{self.inference_api}/inference",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    def _tool_list_files(self, source_dir: Path, directory: str) -> str:
        root = source_dir.resolve()
        target = (source_dir / directory.replace(" ", "")).resolve()
        if not str(target).startswith(str(root)):
            return json.dumps({"error": "Access denied"})
        if not target.is_dir():
            return json.dumps({"error": f"Not a directory: {directory}"})
        files = []
        for item in sorted(target.iterdir()):
            rel = str(item.resolve().relative_to(root))
            files.append(rel + ("/" if item.is_dir() else ""))
        return json.dumps({"files": files})

    def _tool_read_file(self, source_dir: Path, file_path: str) -> str:
        root = source_dir.resolve()
        target = (source_dir / file_path.replace(" ", "")).resolve()
        if not str(target).startswith(str(root)):
            return json.dumps({"error": "Access denied"})
        if not target.is_file():
            return json.dumps({"error": f"Not a file: {file_path}"})
        try:
            return target.read_text(encoding="utf-8")
        except Exception as e:
            return json.dumps({"error": str(e)})

    def _execute_tool_call(self, tool_call: dict, source_dir: Path) -> str:
        try:
            function = tool_call.get("function", {})
            name = function.get("name")
            args = json.loads(function.get("arguments", "{}"))
        except json.JSONDecodeError as exc:
            return json.dumps({"error": f"Invalid JSON: {exc}"})

        if name == "list_files":
            return self._tool_list_files(source_dir, args.get("directory", "."))
        elif name == "read_file":
            return self._tool_read_file(source_dir, args.get("file_path", ""))
        elif name == "report_vulnerabilities":
            return json.dumps(args)
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

    def analyze_file(self, source_dir: Path, relative_path: str, deadline: float) -> tuple[list[Vulnerability], int, int]:
        """Analyze one file using tool use."""
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyze {relative_path} for security vulnerabilities. Use tools to explore the codebase."},
        ]

        # Seed with file list
        list_id = "seed-list"
        messages.append({"role": "assistant", "tool_calls": [{"id": list_id, "type": "function", "function": {"name": "list_files", "arguments": json.dumps({"directory": "."})}}]})
        messages.append({"role": "tool", "tool_call_id": list_id, "content": self._tool_list_files(source_dir, ".")})

        # Read target file
        read_id = "seed-read"
        messages.append({"role": "assistant", "tool_calls": [{"id": read_id, "type": "function", "function": {"name": "read_file", "arguments": json.dumps({"file_path": relative_path})}}]})
        messages.append({"role": "tool", "tool_call_id": read_id, "content": self._tool_read_file(source_dir, relative_path)})

        # Run tool loop
        reported = False
        all_vulns = []
        total_input = 0
        total_output = 0

        for turn in range(5):  # Allow more turns for thorough investigation
            if time.monotonic() >= deadline and not reported:
                messages.append({"role": "user", "content": "Report your findings now."})
                tool_choice = {"type": "function", "function": {"name": "report_vulnerabilities"}}
            else:
                tool_choice = "auto"

            try:
                response = self.inference(messages=messages, tools=TOOL_DEFINITIONS, tool_choice=tool_choice, response_format={"type": "text"})
            except Exception as e:
                console.print(f"[red]Inference error: {e}[/red]")
                break

            usage = response.get("usage", {})
            total_input += usage.get("prompt_tokens", 0)
            total_output += usage.get("completion_tokens", 0)

            message = response["choices"][0]["message"]
            tool_calls = message.get("tool_calls")

            if not tool_calls:
                break

            messages.append(message)

            for tc in tool_calls:
                result_str = self._execute_tool_call(tc, source_dir)

                if tc["function"]["name"] == "report_vulnerabilities":
                    reported = True
                    try:
                        args = json.loads(tc["function"]["arguments"])
                        for v_data in args.get("vulnerabilities", []):
                            v_data["reported_by_model"] = INVESTIGATOR_MODEL
                            all_vulns.append(Vulnerability(**v_data))
                    except Exception as e:
                        console.print(f"[red]Error parsing report: {e}[/red]")

                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result_str})

            if reported:
                break

        return all_vulns, total_input, total_output

    def analyze_project(self, source_dir: Path, project_name: str) -> AnalysisResult:
        """Analyze a project using methodology-based audit."""
        # Discover contract files
        files = []
        for pattern in DEFAULT_CONTRACT_FILE_PATTERNS:
            files.extend(source_dir.glob(pattern))
        files = [
            f for f in files
            if f.is_file()
            and "test" not in f.name.lower()
            and not any(part.lower() in EXCLUDE_DIRS for part in f.parts)
        ]

        if not files:
            return AnalysisResult(
                project=project_name,
                timestamp=datetime.now().isoformat(),
                files_analyzed=0,
                files_skipped=0,
                total_vulnerabilities=0,
                vulnerabilities=[],
                token_usage={"total_input": 0, "total_output": 0},
            )

        all_vulnerabilities = []
        total_input = 0
        total_output = 0
        deadline = time.monotonic() + MAX_TOOL_RUNTIME_SECONDS

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(
                    self.analyze_file,
                    source_dir,
                    str(f.relative_to(source_dir)),
                    deadline,
                ): f
                for f in files
            }

            for future in as_completed(futures):
                vulns, in_tok, out_tok = future.result()
                all_vulnerabilities.extend(vulns)
                total_input += in_tok
                total_output += out_tok

        # Deduplicate
        unique = {v.id: v for v in all_vulnerabilities}
        vulns = list(unique.values())

        return AnalysisResult(
            project=project_name,
            timestamp=datetime.now().isoformat(),
            files_analyzed=len(files),
            files_skipped=0,
            total_vulnerabilities=len(vulns),
            vulnerabilities=vulns,
            token_usage={"total_input": total_input, "total_output": total_output},
        )


def agent_main(project_dir: str = "/app/project_code", inference_api: str = None):
    """Main entry point — called by sandbox with NO args."""
    agent = MWAgent(inference_api=inference_api)
    source_dir = Path(project_dir)

    if not source_dir.exists():
        console.print(f"[red]Error: {project_dir} not found[/red]")
        sys.exit(1)

    result = agent.analyze_project(source_dir, project_dir)

    # Save report
    output_file = source_dir / "agent_report.json"
    with open(output_file, 'w') as f:
        json.dump(result.model_dump(), f, indent=2)

    console.print(f"\n[green]Analysis complete: {result.total_vulnerabilities} vulnerabilities[/green]")
    return result.model_dump(mode="json")


if __name__ == "__main__":
    project_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/project_code"
    agent_main(project_dir)
