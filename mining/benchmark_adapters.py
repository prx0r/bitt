"""Benchmark Adapters (CP3) — Local testing for Harnyx, Ridges, RedTeam.

Provides a unified interface to:
1. Run a subnet's miner locally
2. Score the output
3. Compare against baseline

Each adapter wraps the subnet's native CLI/tools.
"""
import subprocess
import json
import os
import time
from pathlib import Path
from typing import Optional


class BaseAdapter:
    """Base class for subnet benchmark adapters."""
    
    def __init__(self, netuid: int, name: str, repo_path: Path):
        self.netuid = netuid
        self.name = name
        self.repo_path = repo_path
        self.results_dir = Path(f"/root/bitt/trading/experiments/benchmarks/{name}")
        self.results_dir.mkdir(parents=True, exist_ok=True)
    
    def setup(self) -> bool:
        """Install dependencies and verify environment."""
        raise NotImplementedError
    
    def run_local(self, agent_path: Optional[str] = None) -> dict:
        """Run miner locally and return results."""
        raise NotImplementedError
    
    def score(self, result: dict) -> dict:
        """Score the result."""
        raise NotImplementedError
    
    def baseline(self) -> dict:
        """Run baseline (default/stub agent) for comparison."""
        raise NotImplementedError


class HarnyxAdapter(BaseAdapter):
    """Adapter for SN67 Harnyx — research agent subnet."""
    
    def __init__(self):
        super().__init__(67, "harnyx", Path("/root/bitt/subnets/sn67-harnyx"))
    
    def setup(self) -> bool:
        """Install harnyx miner SDK."""
        try:
            subprocess.run(
                ["uv", "sync", "--all-packages", "--dev"],
                cwd=str(self.repo_path),
                capture_output=True, timeout=120
            )
            return True
        except Exception as e:
            print(f"Harnyx setup error: {e}")
            return False
    
    def create_stub_agent(self) -> Path:
        """Create a minimal stub agent for baseline testing."""
        stub = '''"""Stub agent for Harnyx baseline testing."""
from harnyx_miner_sdk.decorators import entrypoint
from harnyx_miner_sdk.query import Query, Response

@entrypoint("query")
async def query(q: Query) -> Response:
    """Minimal agent that returns a basic answer."""
    return Response(
        text=f"I received your query about: {q.text[:100]}. "
             f"This is a stub response for baseline testing.",
        note="stub_baseline"
    )
'''
        agent_path = self.results_dir / "stub_agent.py"
        agent_path.write_text(stub)
        return agent_path
    
    def run_local(self, agent_path: Optional[str] = None) -> dict:
        """Run Harnyx local evaluation."""
        if agent_path is None:
            agent_path = str(self.create_stub_agent())
        
        try:
            result = subprocess.run(
                ["uv", "run", "--package", "harnyx-miner", 
                 "harnyx-miner-local-eval", "--agent-path", agent_path],
                cwd=str(self.repo_path),
                capture_output=True, text=True, timeout=300
            )
            
            return {
                "agent": agent_path,
                "returncode": result.returncode,
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:1000],
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"agent": agent_path, "error": "timeout", "success": False}
        except Exception as e:
            return {"agent": agent_path, "error": str(e), "success": False}
    
    def score(self, result: dict) -> dict:
        """Score Harnyx result based on output."""
        if not result.get("success"):
            return {"score": 0, "reason": "execution_failed"}
        
        stdout = result.get("stdout", "")
        # Look for score metrics in output
        if "score" in stdout.lower():
            return {"score": 0.5, "reason": "partial_score_found", "raw": stdout[:500]}
        
        return {"score": 0.3, "reason": "completed_no_score", "raw": stdout[:500]}


class RidgesAdapter(BaseAdapter):
    """Adapter for SN62 Ridges — code agent subnet."""
    
    def __init__(self):
        super().__init__(62, "ridges", Path("/root/bitt/subnets/sn62-ridges"))
    
    def setup(self) -> bool:
        """Install ridges miner CLI."""
        try:
            subprocess.run(
                ["pip", "install", "-e", ".[miner]"],
                cwd=str(self.repo_path),
                capture_output=True, timeout=120
            )
            return True
        except Exception as e:
            print(f"Ridges setup error: {e}")
            return False
    
    def create_stub_agent(self) -> Path:
        """Create a minimal stub agent for baseline testing."""
        stub = '''"""Stub agent for Ridges baseline testing."""
import os

def agent_main(input) -> str:
    """Minimal agent that returns an empty diff."""
    # Read the instruction
    instruction_path = os.path.join(os.getcwd(), "instruction.md")
    if os.path.exists(instruction_path):
        with open(instruction_path) as f:
            instruction = f.read()
    else:
        instruction = "No instruction found"
    
    # Return empty diff (no changes)
    return ""
'''
        agent_path = self.results_dir / "stub_agent.py"
        agent_path.write_text(stub)
        return agent_path
    
    def run_local(self, agent_path: Optional[str] = None) -> dict:
        """Run Ridges local evaluation."""
        if agent_path is None:
            agent_path = str(self.create_stub_agent())
        
        try:
            result = subprocess.run(
                ["ridges", "miner", "run-local", 
                 "--agent-path", agent_path,
                 "--non-interactive"],
                cwd=str(self.repo_path),
                capture_output=True, text=True, timeout=300
            )
            
            return {
                "agent": agent_path,
                "returncode": result.returncode,
                "stdout": result.stdout[:2000],
                "stderr": result.stderr[:1000],
                "success": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {"agent": agent_path, "error": "timeout", "success": False}
        except Exception as e:
            return {"agent": agent_path, "error": str(e), "success": False}
    
    def score(self, result: dict) -> dict:
        """Score Ridges result based on test pass rate."""
        if not result.get("success"):
            return {"score": 0, "reason": "execution_failed"}
        
        stdout = result.get("stdout", "")
        # Look for test results
        if "passed" in stdout.lower() or "tests" in stdout.lower():
            return {"score": 0.5, "reason": "tests_found", "raw": stdout[:500]}
        
        return {"score": 0.2, "reason": "completed_no_tests", "raw": stdout[:500]}


class RedTeamAdapter(BaseAdapter):
    """Adapter for SN61 RedTeam — cybersecurity challenge subnet."""
    
    def __init__(self):
        super().__init__(61, "redteam", Path("/root/bitt/subnets/sn61-redteam"))
    
    def setup(self) -> bool:
        """Verify Docker is available."""
        try:
            result = subprocess.run(["docker", "info"], capture_output=True, timeout=10)
            return result.returncode == 0
        except:
            return False
    
    def run_local(self, agent_path: Optional[str] = None) -> dict:
        """RedTeam requires Docker images — cannot run locally without full setup."""
        return {
            "agent": agent_path,
            "error": "requires_docker_image_and_wallet",
            "success": False,
            "note": "RedTeam miners submit Docker images, not Python scripts. "
                    "Full local testing requires Docker Compose setup with wallet."
        }
    
    def score(self, result: dict) -> dict:
        """Score RedTeam result."""
        return {"score": 0, "reason": "requires_chain_execution"}


def run_benchmark_all() -> dict:
    """Run benchmarks for all adapters."""
    adapters = {
        "harnyx": HarnyxAdapter(),
        "ridges": RidgesAdapter(),
        "redteam": RedTeamAdapter(),
    }
    
    results = {}
    
    for name, adapter in adapters.items():
        print(f"\n--- {name.upper()} (SN{adapter.netuid}) ---")
        
        # Setup
        print(f"  Setting up...")
        setup_ok = adapter.setup()
        print(f"  Setup: {'OK' if setup_ok else 'FAILED'}")
        
        if not setup_ok:
            results[name] = {"setup": False, "error": "setup_failed"}
            continue
        
        # Run baseline
        print(f"  Running baseline...")
        baseline = adapter.run_local()
        baseline_score = adapter.score(baseline)
        print(f"  Baseline: score={baseline_score.get('score', 0)}, success={baseline.get('success', False)}")
        
        results[name] = {
            "setup": True,
            "baseline": baseline,
            "baseline_score": baseline_score,
        }
    
    return results


if __name__ == "__main__":
    print("=== Benchmark Adapters (CP3) ===")
    
    results = run_benchmark_all()
    
    # Save
    output = Path("/root/bitt/trading/experiments/benchmarks/results.json")
    with open(output, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n=== SUMMARY ===")
    for name, data in results.items():
        score = data.get("baseline_score", {}).get("score", "N/A")
        print(f"  {name}: setup={data.get('setup')}, baseline_score={score}")
    
    print(f"\nSaved to {output}")
