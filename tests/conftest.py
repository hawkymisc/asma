"""Pytest configuration and shared fixtures."""
import pytest


@pytest.fixture
def sample_skill_md() -> str:
    """Return a valid SKILL.md content."""
    return """---
name: test-skill
description: A test skill for validation
---

# Test Skill

## Instructions
This is a test skill for testing purposes.

## Examples
- Example 1
- Example 2

## Guidelines
- Guideline 1
- Guideline 2
"""


@pytest.fixture
def invalid_skill_md_no_frontmatter() -> str:
    """Return SKILL.md without frontmatter."""
    return """# Test Skill

Just a heading, no frontmatter.
"""


@pytest.fixture
def invalid_skill_md_missing_name() -> str:
    """Return SKILL.md with missing name field."""
    return """---
description: A test skill
---

# Test Skill
"""


@pytest.fixture
def invalid_skill_md_bad_name_format() -> str:
    """Return SKILL.md with invalid name format."""
    return """---
name: Invalid_Name_With_Underscores
description: A test skill
---

# Test Skill
"""


@pytest.fixture
def sample_skillset_yaml() -> str:
    """Return a valid skillset.yaml content."""
    return """config:
  auto_update: false
  parallel_downloads: 4

global:
  - name: document-analyzer
    source: github:anthropics/skills/document-analyzer
    version: v1.0.0

  - name: python-expert
    source: github:travisvn/awesome-claude-skills/python-expert
    ref: main

project:
  - name: test-runner
    source: github:anthropics/skills/test-runner
    version: v2.1.0

  - name: local-skill
    source: local:~/my-skills/local-skill
"""
