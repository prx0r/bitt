"""Simple v1 — Matching official BitSec baseline pattern.

Key differences from mw-audit-v1:
1. Simple system prompt (not complex methodology)
2. Direct tool calls (no token budget, no empty report tracking)
3. Reports findings immediately after each file
4. Only 3 turns per file (like official baseline)
5. Uses response_format={"type": "text"} for tool calls
6. Simple deduplication by hash at the end
"""
import hashlib
import json
import os
import requests
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from enum import Enum
from pathlib import Path
from textwrap import dedent
from typing import Any

from pydantic import BaseModel
from rich.console import Console

console = Console()

# Config
MAX_WORKERS = 2
MAX_TOOL_RUNTIME_SECONDS = 5 * 60
DEFAULT_CONTRACT_FILE_PATTERNS = ['**/*.sol', '**/*.vy', '**/*.cairo', '**/*.rs', '**/*.move']
EXCLUDE_DIRS = {"testing", "mocks", "examples", "interfaces", "script", "broadcast", "libraries"}

JSON_MODEL = "mimo-v2.5"

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory path relative to project root"}
                },
                "required": ["directory"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file contents",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "File path relative to project root"}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "report_vulnerabilities",
            "description": "Report vulnerabilities found",
            "parameters": {
                "type": "object",
                "properties": {
                    "vulnerabilities": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "description": {"type": "string"},
                                "vulnerability_type": {"type": "string"},
                                "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                                "confidence": {"type": "number"},
                                "location": {"type": "string"},
                                "file": {"type": "string"}
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


class SimpleAgent:
    def __init__(self, config: dict[str, Any] | None = None, inference_api: str = None):
        self.config = config or {"model": JSON_MODEL}
        self.inference_api = inference_api or os.getenv('INFERENCE_API', "http://bitsec_proxy:8000")
        self.agent_id = os.getenv('AGENT_ID', "unknown")
        self.job_run_id = os.getenv('JOB_RUN_ID', "unknown")
        self.inference_api_key = os.getenv('INFERENCE_API_KEY')
        if not self.inference_api_key:
            console.print("[yellow]WARNING: No INFERENCE_API_KEY set[/yellow]")

    def inference(self, messages: list[dict[str, Any]], **kwargs) -> dict[str, Any]:
        """Call inference through proxy."""
        for message in messages:
            if message.get("role") == "assistant" and 'tool_call_id' in message:
                message.pop("tool_call_id", None)

        payload = {
            "model": self.config['model'],
            "messages": messages,
            "max_tokens": 8192,
        }
        payload.update(kwargs)

        try:
            headers = {
                "x-inference-api-key": self.inference_api_key or "",
                "x-agent-id": self.agent_id,
                "x-job-run-id": self.job_run_id,
                "x-request-phase": "execution",
            }
            resp = requests.post(
                f"{self.inference_api}/inference",
                headers=headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            return self._inference_direct(messages, **kwargs)

    def _inference_direct(self, messages: list[dict[str, Any]], **kwargs) -> dict[str, Any]:
        """Direct API call for local testing."""
        import sys
        sys.path.insert(0, str(Path("/root/bitt")))
        sys.path.insert(0, str(Path("/root/bitt/workers/bitsec")))
        from opencode_harness import call_model

        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "tool":
                prompt_parts.append(f"Tool result: {content}")

        prompt = "\n\n".join(prompt_parts)
        result = call_model("mimo-v2.5", prompt, max_tokens=8192)

        content = result.get("content", "")
        try:
            data = json.loads(content)
            return {"choices": [{"message": {"content": content, "tool_calls": None}}], "usage": {"prompt_tokens": 0, "completion_tokens": 0}}
        except:
            return {"choices": [{"message": {"content": content, "tool_calls": None}}], "usage": {"prompt_tokens": 0, "completion_tokens": 0}}

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

    def _discover_contract_files(self, source_dir: Path) -> list[Path]:
        files = []
        for pattern in DEFAULT_CONTRACT_FILE_PATTERNS:
            files.extend(source_dir.glob(pattern))
        return [
            f for f in files
            if f.is_file()
            and "test" not in f.name.lower()
            and not any(part.lower() in EXCLUDE_DIRS for part in f.parts)
        ]

    def _analyze_file_with_tools(self, source_dir: Path, relative_path: str, deadline: float) -> tuple[list[Vulnerability], int, int]:
        """Analyze one file using tool use — matches official baseline pattern."""
        messages = [
            {"role": "system", "content": dedent("""\
                You are a senior smart contract security auditor.
                Analyze code for security vulnerabilities.
                Use tools to explore the project and read files.
                IMPORTANT: Keep your reasoning under 1500 tokens. After analyzing the file, immediately call report_vulnerabilities.""")},
            {"role": "user", "content": f"Analyze {relative_path} for vulnerabilities"},
        ]

        # Seed with file list
        list_id = "seed-list"
        messages.append({"role": "assistant", "tool_calls": [{"id": list_id, "type": "function", "function": {"name": "list_files", "arguments": json.dumps({"directory": "."})}}]})
        messages.append({"role": "tool", "tool_call_id": list_id, "content": self._tool_list_files(source_dir, ".")})

        # Read target file
        read_id = "seed-read"
        messages.append({"role": "assistant", "tool_calls": [{"id": read_id, "type": "function", "function": {"name": "read_file", "arguments": json.dumps({"file_path": relative_path})}}]})
        messages.append({"role": "tool", "tool_call_id": read_id, "content": self._tool_read_file(source_dir, relative_path)})

        # Run tool loop — 3 turns like official baseline
        reported = False
        all_vulns = []
        total_input = 0
        total_output = 0

        for turn in range(3):
            if time.monotonic() >= deadline and not reported:
                messages.append({"role": "user", "content": "Report NOW"})
                tool_choice = {"type": "function", "function": {"name": "report_vulnerabilities"}}
            elif turn == 2 and not reported:
                tool_choice = {"type": "function", "function": {"name": "report_vulnerabilities"}}
            else:
                tool_choice = "auto"

            response = self.inference(messages=messages, tools=TOOL_DEFINITIONS, tool_choice=tool_choice, response_format={"type": "text"})

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
                            v_data["reported_by_model"] = self.config["model"]
                            all_vulns.append(Vulnerability(**v_data))
                    except Exception as e:
                        console.print(f"[red]Error parsing report: {e}[/red]")

                messages.append({"role": "tool", "tool_call_id": tc["id"], "content": result_str})

            if reported:
                break

        return all_vulns, total_input, total_output

    def analyze_project(self, source_dir: Path, project_name: str) -> AnalysisResult:
        """Analyze a project using tool use — matches official baseline pattern."""
        contract_files = self._discover_contract_files(source_dir)

        if not contract_files:
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
        files_analyzed = 0
        deadline = time.monotonic() + MAX_TOOL_RUNTIME_SECONDS

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {
                executor.submit(
                    self._analyze_file_with_tools,
                    source_dir,
                    str(f.relative_to(source_dir)),
                    deadline,
                ): f
                for f in contract_files
            }

            for future in as_completed(futures):
                vulns, in_tok, out_tok = future.result()
                all_vulnerabilities.extend(vulns)
                total_input += in_tok
                total_output += out_tok
                files_analyzed += 1

        # Deduplicate
        unique = {v.id: v for v in all_vulnerabilities}
        vulns = list(unique.values())

        return AnalysisResult(
            project=project_name,
            timestamp=datetime.now().isoformat(),
            files_analyzed=files_analyzed,
            files_skipped=0,
            total_vulnerabilities=len(vulns),
            vulnerabilities=vulns,
            token_usage={"total_input": total_input, "total_output": total_output},
        )


def agent_main(project_dir: str = "/app/project_code", inference_api: str = None):
    """Main entry point — called by sandbox with NO args."""
    agent = SimpleAgent(inference_api=inference_api)
    source_dir = Path(project_dir)

    if not source_dir.exists():
        console.print(f"[red]Error: {project_dir} not found[/red]")
        sys.exit(1)

    result = agent.analyze_project(source_dir, project_dir)

    # Save report locally
    output_file = source_dir / "agent_report.json"
    with open(output_file, 'w') as f:
        json.dump(result.model_dump(), f, indent=2)

    console.print(f"\n[green]Analysis complete: {result.total_vulnerabilities} vulnerabilities[/green]")
    return result.model_dump(mode="json")


if __name__ == "__main__":
    project_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/project_code"
    agent_main(project_dir)
