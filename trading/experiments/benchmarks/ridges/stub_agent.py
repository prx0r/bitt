"""Stub agent for Ridges baseline testing."""
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
