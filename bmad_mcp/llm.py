"""LLM CLI wrapper for multi-provider support."""

import os
import subprocess
import tempfile
from pathlib import Path


# Default models - must match llm CLI format: anthropic/model-name
DEFAULT_CLAUDE_MODEL = "anthropic/claude-sonnet-4-5"
DEFAULT_REVIEW_MODEL = "anthropic/claude-opus-4-0"
DEFAULT_TIMEOUT = 300


def get_model(env_var: str, default: str) -> str:
    """Get model from environment variable or use default."""
    return os.environ.get(env_var, default)


def get_timeout() -> int:
    """Get LLM timeout from environment."""
    try:
        return int(os.environ.get("LLM_TIMEOUT", DEFAULT_TIMEOUT))
    except (ValueError, TypeError):
        return DEFAULT_TIMEOUT


def call_llm(
    prompt: str,
    system_prompt: str | None = None,
    model: str | None = None,
    context: str | None = None,
    timeout: int | None = None,
) -> str:
    """Call LLM via llm CLI.

    Args:
        prompt: The user prompt
        system_prompt: System prompt (optional)
        model: Model to use (defaults to CLAUDE_MODEL env var)
        context: Context to pipe to stdin (optional)
        timeout: Timeout in seconds (defaults to LLM_TIMEOUT env var)

    Returns:
        LLM response text

    Raises:
        RuntimeError: If LLM call fails or times out
    """
    if model is None:
        model = get_model("CLAUDE_MODEL", DEFAULT_CLAUDE_MODEL)
    if timeout is None:
        timeout = get_timeout()

    # Build command
    cmd = ["llm", "-m", model]

    if system_prompt:
        cmd.extend(["-s", system_prompt])

    cmd.append(prompt)

    # Determine timeout command
    timeout_cmd = _get_timeout_command()
    if timeout_cmd:
        cmd = [timeout_cmd, str(timeout)] + cmd

    # Use temp files to prevent memory exhaustion from massive outputs
    with tempfile.TemporaryFile(mode='w+') as out_f, tempfile.TemporaryFile(mode='w+') as err_f:
        try:
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE if context else None,
                stdout=out_f,
                stderr=err_f,
                text=True,
            )

            if context:
                try:
                    process.stdin.write(context)
                    process.stdin.close()
                except BrokenPipeError:
                    pass  # Process died early

            try:
                process.wait(timeout=timeout + 10)
            except subprocess.TimeoutExpired:
                process.kill()
                raise RuntimeError(f"LLM call timed out after {timeout}s")

            # Limit output read to 1MB to prevent memory exhaustion
            out_f.seek(0)
            err_f.seek(0)
            stdout = out_f.read(1_000_000)
            stderr = err_f.read(1_000_000)

            if process.returncode == 124:
                raise RuntimeError(f"LLM call timed out after {timeout}s")

            if process.returncode != 0:
                raise RuntimeError(f"LLM call failed: {stderr.strip()}")

            return stdout.strip()

        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"LLM call failed: {e}")


def _get_timeout_command() -> str | None:
    """Get the timeout command (gtimeout on macOS, timeout on Linux)."""
    import shutil

    if shutil.which("gtimeout"):
        return "gtimeout"
    elif shutil.which("timeout"):
        return "timeout"
    return None


def check_llm_available() -> tuple[bool, str | None]:
    """Check if llm CLI is available and configured.

    Returns:
        (is_available, error_message)
    """
    import shutil

    if not shutil.which("llm"):
        return False, "llm CLI not found. Install with: pip install llm"

    # Check if any models are available
    try:
        result = subprocess.run(
            ["llm", "models"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False, f"llm models check failed: {result.stderr}"
    except Exception as e:
        return False, f"llm check failed: {e}"

    return True, None
