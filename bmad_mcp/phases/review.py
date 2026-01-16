"""Code review phase - adversarial review using LLM."""

import re
import subprocess
from pathlib import Path

from ..llm import call_llm, get_model, DEFAULT_REVIEW_MODEL
from ..project import ProjectPaths, get_default_branch


def validate_branch_name(branch: str) -> bool:
    """Validate branch name contains only safe characters.

    Prevents command injection via malicious branch names that could
    be interpreted as git flags (e.g., --version, -v).
    """
    if not branch:
        return False
    # Only allow alphanumeric, dots, underscores, hyphens, and forward slashes
    # Must not start with a hyphen (could be interpreted as a flag)
    return bool(re.match(r'^[a-zA-Z0-9._/][a-zA-Z0-9._/-]*$', branch))


SYSTEM_PROMPT = """You are an ADVERSARIAL Senior Developer performing code review.

You are reviewing ONLY the git diff below. Focus on the actual code changes.

Your job is to find 3-10 specific issues in the code that was written.
You MUST find issues - 'looks good' is NOT acceptable.

Review for:
1. Code quality and patterns
2. Test coverage gaps
3. Security issues (injection, XSS, auth bypasses)
4. Performance concerns
5. Error handling and edge cases

For each issue found:
- Describe the problem specifically
- Reference the file and line number from the diff
- Suggest the fix
- Rate severity: CRITICAL, HIGH, MEDIUM, LOW

IMPORTANT: Only reference files and lines that appear in the diff.
Do NOT invent issues about code that isn't shown.

Output a structured review report in markdown format."""


def get_git_diff(project_root: Path, base_branch: str | None = None) -> str:
    """Get git diff from base branch, focusing on code files.

    Args:
        project_root: Project root directory
        base_branch: Base branch to compare against (auto-detected if None)

    Returns:
        Git diff output (code files only, excludes .md, .yaml, .bak)
    """
    if base_branch is None:
        base_branch = get_default_branch(project_root)

    # Validate branch name to prevent command injection
    if not validate_branch_name(base_branch):
        raise ValueError(f"Invalid branch name: {base_branch}")

    # Use origin/ prefix to compare against remote (handles case where we're on the base branch)
    remote_branch = f"origin/{base_branch}"

    # Exclusions for non-code files (focus review on actual implementation)
    exclusions = [
        ":!*.md",
        ":!*.yaml",
        ":!*.yml",
        ":!*.bak",
        ":!*.bak.*",
        ":!docs/*",
    ]

    try:
        # Get diff stats (code files only)
        stats = subprocess.run(
            ["git", "diff", remote_branch, "--stat", "--"] + exclusions,
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        # Get full diff (code files only)
        diff = subprocess.run(
            ["git", "diff", remote_branch, "--"] + exclusions,
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        # If remote branch doesn't exist, fall back to local branch
        if stats.returncode != 0 or "unknown revision" in stats.stderr.lower():
            stats = subprocess.run(
                ["git", "diff", base_branch, "--stat", "--"] + exclusions,
                cwd=project_root,
                capture_output=True,
                text=True,
            )
            diff = subprocess.run(
                ["git", "diff", base_branch, "--"] + exclusions,
                cwd=project_root,
                capture_output=True,
                text=True,
            )

        if stats.returncode != 0 or diff.returncode != 0:
            raise RuntimeError("git diff failed")

        result = f"{stats.stdout}\n\n{diff.stdout}".strip()
        if not result or result == "\n\n":
            return "No code changes found (only documentation/config changes)"

        return result

    except Exception:
        raise


"""Code review phase - adversarial review using LLM."""

import re
import subprocess
from pathlib import Path

from ..llm import call_llm, get_model, DEFAULT_REVIEW_MODEL
from ..project import ProjectPaths, get_default_branch


def validate_branch_name(branch: str) -> bool:
    """Validate branch name contains only safe characters.

    Prevents command injection via malicious branch names that could
    be interpreted as git flags (e.g., --version, -v).
    """
    if not branch:
        return False
    # Only allow alphanumeric, dots, underscores, hyphens, and forward slashes
    # Must not start with a hyphen (could be interpreted as a flag)
    return bool(re.match(r'^[a-zA-Z0-9._/][a-zA-Z0-9._/-]*$', branch))


SYSTEM_PROMPT = """You are an ADVERSARIAL Senior Developer performing code review.

You are reviewing ONLY the git diff below. Focus on the actual code changes.

Your job is to find 3-10 specific issues in the code that was written.
You MUST find issues - 'looks good' is NOT acceptable.

Review for:
1. Code quality and patterns
2. Test coverage gaps
3. Security issues (injection, XSS, auth bypasses)
4. Performance concerns
5. Error handling and edge cases

For each issue found:
- Describe the problem specifically
- Reference the file and line number from the diff
- Suggest the fix
- Rate severity: CRITICAL, HIGH, MEDIUM, LOW

IMPORTANT: Only reference files and lines that appear in the diff.
Do NOT invent issues about code that isn't shown.

Output a structured review report in markdown format."""


def get_git_diff(project_root: Path, base_branch: str | None = None) -> str:
    """Get git diff from base branch, focusing on code files.

    Args:
        project_root: Project root directory
        base_branch: Base branch to compare against (auto-detected if None)

    Returns:
        Git diff output (code files only, excludes .md, .yaml, .bak)
    """
    if base_branch is None:
        base_branch = get_default_branch(project_root)

    # Validate branch name to prevent command injection
    if not validate_branch_name(base_branch):
        raise ValueError(f"Invalid branch name: {base_branch}")

    # Use origin/ prefix to compare against remote (handles case where we're on the base branch)
    remote_branch = f"origin/{base_branch}"

    # Exclusions for non-code files (focus review on actual implementation)
    exclusions = [
        ":!*.md",
        ":!*.yaml",
        ":!*.yml",
        ":!*.bak",
        ":!*.bak.*",
        ":!docs/*",
    ]

    try:
        # Get diff stats (code files only)
        stats = subprocess.run(
            ["git", "diff", remote_branch, "--stat", "--"] + exclusions,
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        # Get full diff (code files only)
        diff = subprocess.run(
            ["git", "diff", remote_branch, "--"] + exclusions,
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        # If remote branch doesn't exist, fall back to local branch
        if stats.returncode != 0 or "unknown revision" in stats.stderr.lower():
            stats = subprocess.run(
                ["git", "diff", base_branch, "--stat", "--"] + exclusions,
                cwd=project_root,
                capture_output=True,
                text=True,
            )
            diff = subprocess.run(
                ["git", "diff", base_branch, "--"] + exclusions,
                cwd=project_root,
                capture_output=True,
                text=True,
            )

        if stats.returncode != 0 or diff.returncode != 0:
            raise RuntimeError("git diff failed")

        result = f"{stats.stdout}\n\n{diff.stdout}".strip()
        if not result or result == "\n\n":
            return "No code changes found (only documentation/config changes)"

        return result

    except Exception:
        raise


def _strip_code_blocks(text: str) -> str:
    """Strip fenced code blocks to prevent regex false positives."""
    return re.sub(r'```[\s\S]*?```', '', text)


def parse_review_issues(review_content: str) -> list[dict]:
    """Parse structured issues from review markdown.

    Handles multiple LLM output formats:
    - **CRITICAL**: description
    - CRITICAL: description
    - ### CRITICAL
    - - CRITICAL - description
    - [CRITICAL] description
    """
    issues = []
    
    # Strip code blocks to avoid parsing content inside code examples
    content_to_parse = _strip_code_blocks(review_content)

    # Multiple patterns to match different LLM output formats
    patterns = [
        # **CRITICAL**: description or **CRITICAL** description
        r'\*\*(CRITICAL|HIGH|MEDIUM|LOW)\*\*[:\s]*(.+?)(?=\*\*(?:CRITICAL|HIGH|MEDIUM|LOW)\*\*|\n##|\n\*\*[A-Z]+\*\*|$)',
        # CRITICAL: description (plain text)
        r'(?:^|\n)(CRITICAL|HIGH|MEDIUM|LOW)[:\s]+(.+?)(?=\n(?:CRITICAL|HIGH|MEDIUM|LOW)[:\s]|\n##|$)',
        # ### CRITICAL or ## CRITICAL (header style)
        r'#{2,3}\s*(CRITICAL|HIGH|MEDIUM|LOW)[:\s]*\n(.+?)(?=\n#{2,3}|$)',
        # [CRITICAL] description (bracket style)
        r'\[(CRITICAL|HIGH|MEDIUM|LOW)\][:\s]*(.+?)(?=\[(?:CRITICAL|HIGH|MEDIUM|LOW)\]|\n##|$)',
        # - CRITICAL - or * CRITICAL: (list style)
        r'[-*]\s*(CRITICAL|HIGH|MEDIUM|LOW)\s*[-:]\s*(.+?)(?=\n[-*]\s*(?:CRITICAL|HIGH|MEDIUM|LOW)|$)',
        # Numbered: 1. **CRITICAL**: or 1. CRITICAL:
        r'\d+\.\s*\*{0,2}(CRITICAL|HIGH|MEDIUM|LOW)\*{0,2}[:\s]+(.+?)(?=\n\d+\.\s*\*{0,2}(?:CRITICAL|HIGH|MEDIUM|LOW)|$)',
    ]

    seen_issues = set()  # Deduplicate

    for pattern in patterns:
        for match in re.finditer(pattern, content_to_parse, re.DOTALL | re.IGNORECASE):
            severity = match.group(1).upper()
            content = match.group(2).strip()

            # Try to extract file reference first to use in dedup key
            file_patterns = [
                r'[`\'"]([a-zA-Z0-9_/.-]+\.[a-zA-Z]+)[`\'"]?[:\s]*(?:line\s*)?(\d+)?',
                r'\(([a-zA-Z0-9_/.-]+\.[a-zA-Z]+),?\s*(?:line\s*)?(\d+)?\)',
                r'(?:in|at|file)\s+([a-zA-Z0-9_/.-]+\.[a-zA-Z]+)(?:[:\s]+(?:line\s*)?(\d+))?',
            ]

            file_path = None
            line_num = None
            for fp in file_patterns:
                file_match = re.search(fp, content, re.IGNORECASE)
                if file_match:
                    file_path = file_match.group(1)
                    line_num = file_match.group(2) if len(file_match.groups()) > 1 else None
                    break

            # Stronger deduplication key: severity + file + line + start of content
            # This prevents dropping distinct findings that start similarly
            dedup_key = f"{severity}:{file_path}:{line_num}:{content[:50]}"
            if dedup_key in seen_issues:
                continue
            seen_issues.add(dedup_key)

            # Get first line as problem summary
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            problem = lines[0] if lines else content[:100]

            # Look for suggested fix with various keywords
            fix_keywords = r'(?:fix|solution|suggest|change|should|instead|replace|use)[:\s]*(.+?)(?:\n|$)'
            fix_match = re.search(fix_keywords, content, re.IGNORECASE)
            fix = fix_match.group(1).strip() if fix_match else None

            issues.append({
                "severity": severity,
                "problem": problem,
                "file": file_path,
                "line": int(line_num) if line_num else None,
                "suggested_fix": fix,
                "full_context": content[:500],
            })

    return issues


def review_story(project: ProjectPaths, story_key: str) -> dict:
    """Run adversarial code review.

    Args:
        project: Project paths
        story_key: Story key being reviewed

    Returns:
        Dictionary with review results
    """
    # Get git diff - this is the ONLY thing we review
    # Do NOT include story content - it causes LLM to review spec instead of code
    try:
        diff_content = get_git_diff(project.root)
    except Exception as e:
        return {
            "story_key": story_key,
            "review": f"Review failed: {e}",
            "has_critical_issues": True,
            "recommendation": "in-progress",
            "structured_issues": [
                {
                    "severity": "CRITICAL",
                    "problem": f"Review failed before analysis: {e}",
                    "file": None,
                    "line": None,
                    "suggested_fix": "Fix git configuration or diff generation before retrying.",
                    "full_context": str(e),
                }
            ],
        }

    # Context is ONLY the diff - no story content
    context = diff_content

    # Call LLM for review
    model = get_model("REVIEW_MODEL", DEFAULT_REVIEW_MODEL)

    review = call_llm(
        prompt=f"Perform adversarial code review for story: {story_key}",
        system_prompt=SYSTEM_PROMPT,
        model=model,
        context=context,
    )

    # Check for critical issues using structured parsing
    structured_issues = parse_review_issues(review)
    
    # Determine if there are critical issues based on parsed results
    has_critical = any(i['severity'] == 'CRITICAL' for i in structured_issues)

    return {
        "story_key": story_key,
        "review": review,
        "has_critical_issues": has_critical,
        "recommendation": "in-progress" if has_critical else "done",
        "structured_issues": structured_issues,
    }


def save_review(project: ProjectPaths, story_key: str, review_content: str) -> Path:
    """Save review to file.

    Args:
        project: Project paths
        story_key: Story key
        review_content: Review markdown content

    Returns:
        Path to saved review file
    """
    reviews_dir = project.stories_dir / "reviews"
    reviews_dir.mkdir(exist_ok=True)

    review_file = reviews_dir / f"{story_key}-review.md"
    review_file.write_text(review_content)

    return review_file
