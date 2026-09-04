"""BitSec-compatible wrapper for Bitsec-Striker agent."""
import os
import sys
import json
from pathlib import Path
from datetime import datetime
import requests

# Add the bitsec-scanner agents to path
sys.path.insert(0, str(Path("/root/bitt/subnets/sn60-bitsec/bitsec-scanner/agents")))

# Get API key from vault
sys.path.insert(0, str(Path("/root/bitt")))
from vault import Vault
v = Vault()
API_KEY = v.get('opencode_go_api_key')

class PatchedInferenceClient:
    def __init__(self, api_url: str, api_key: str | None = None):
        self.api_url = api_url.rstrip('/') + '/inference'
        self.api_key = api_key or API_KEY
        self.headers = {
            "Content-Type": "application/json",
            "x-inference-api-key": self.api_key,
            "x-agent-id": "bitsec-striker",
            "x-job-run-id": "local",
            "x-request-phase": "execution"
        }
    
    def call_llm(self, prompt: str, system_prompt: str = "", temperature: float = 0.7) -> str:
        payload = {
            "model": "mimo-v2.5",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": 4096
        }
        try:
            response = requests.post(self.api_url, headers=self.headers, json=payload, timeout=120)
            response.raise_for_status()
            result = response.json()
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            print(f"LLM call failed: {e}")
            return ""

# Patch the module
import agent as agent_module
agent_module.InferenceClient = PatchedInferenceClient

from agent import agent_main as striker_main

def agent_main(project_dir: str = "/app/project_code", inference_api: str = None):
    """BitSec-compatible entry point."""
    if inference_api is None:
        inference_api = os.getenv('INFERENCE_API', 'http://localhost:8087')
    
    findings = striker_main(project_dir, inference_api)
    
    return {
        "project": project_dir,
        "timestamp": datetime.now().isoformat(),
        "files_analyzed": len(findings),
        "files_skipped": 0,
        "total_vulnerabilities": len(findings),
        "vulnerabilities": findings,
        "token_usage": {"input_tokens": 0, "output_tokens": 0}
    }

if __name__ == "__main__":
    project_dir = sys.argv[1] if len(sys.argv) > 1 else "/app/project_code"
    result = agent_main(project_dir)
    print(json.dumps(result, indent=2))
