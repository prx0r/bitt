"""Pool Knowledge Loader — connects security worker to pool shared knowledge.

Loads doctrine, skills, and findings from the security pool.
Injects relevant context into worker prompts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

POOL_DIR = Path("/root/bitt/private-lab/lab/pools/security")


def load_doctrine() -> str:
    """Load security pool doctrine."""
    doctrine_path = POOL_DIR / "doctrine" / "core.md"
    if doctrine_path.exists():
        return doctrine_path.read_text()
    return ""


def load_skills(max_skills: int = 3) -> list[dict]:
    """Load security pool skills."""
    skills_dir = POOL_DIR / "skills"
    if not skills_dir.exists():
        return []

    skills = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if skill_dir.is_dir():
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                skills.append({
                    "name": skill_dir.name,
                    "content": skill_file.read_text()[:2000],
                })
                if len(skills) >= max_skills:
                    break
    return skills


def load_primitives() -> dict:
    """Load security primitives registry."""
    primitives_path = Path("/root/bitt/lab-interfaces/pools/security/primitives.yaml")
    if not primitives_path.exists():
        return {}
    try:
        import yaml
        with open(primitives_path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def build_context_pack(task_description: str = "", max_tokens: int = 4000) -> str:
    """Build a context pack from pool knowledge for injection into prompts.

    Returns a string that can be prepended to worker prompts.
    """
    parts = []

    # 1. Doctrine (always included)
    doctrine = load_doctrine()
    if doctrine:
        parts.append(f"## Security Doctrine\n\n{doctrine}")

    # 2. Skills (relevant to task)
    skills = load_skills(max_skills=2)
    for skill in skills:
        parts.append(f"## Skill: {skill['name']}\n\n{skill['content'][:1000]}")

    # 3. Truncate to budget
    context = "\n\n---\n\n".join(parts)
    if len(context) > max_tokens * 4:  # rough char estimate
        context = context[:max_tokens * 4]

    return context


def build_prompt_with_pool_knowledge(
    base_prompt: str,
    task_description: str = "",
    include_doctrine: bool = True,
    include_skills: bool = True,
) -> str:
    """Build a prompt enriched with pool shared knowledge."""
    pool_context = ""

    if include_doctrine:
        doctrine = load_doctrine()
        if doctrine:
            pool_context += f"\n\n## Security Principles (from pool doctrine)\n{doctrine}"

    if include_skills:
        skills = load_skills(max_skills=1)
        for skill in skills:
            pool_context += f"\n\n## Methodology: {skill['name']}\n{skill['content'][:800]}"

    if pool_context:
        return f"{pool_context}\n\n---\n\n{base_prompt}"
    return base_prompt
