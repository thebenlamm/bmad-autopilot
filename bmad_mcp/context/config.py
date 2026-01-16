"""Configuration loader for BMAD context."""

import yaml
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ContextConfig:
    """Configuration for context indexing."""
    enabled: bool = True
    file_patterns: list[str] = field(default_factory=lambda: [
        "**/*.py", "**/*.js", "**/*.ts", "**/*.tsx", 
        "**/*.go", "**/*.java", "**/*.rb"
    ])
    ignore_patterns: list[str] = field(default_factory=lambda: [
        "**/node_modules/**", "**/venv/**", "**/.venv/**", 
        "**/dist/**", "**/build/**", "**/__pycache__/**", 
        "**/*.min.js", "**/*.test.*", "**/*_test.go"
    ])
    max_results: int = 5
    staleness_threshold: int = 3600  # seconds


def load_config(project_root: Path) -> ContextConfig:
    """Load configuration from .bmad/config.yaml.
    
    Args:
        project_root: Project root directory
        
    Returns:
        ContextConfig object (with defaults if file missing)
    """
    config_file = project_root / ".bmad" / "config.yaml"
    
    if not config_file.exists():
        return ContextConfig()
        
    try:
        content = yaml.safe_load(config_file.read_text())
        if not content:
            return ContextConfig()
            
        if "context" not in content:
            logger.debug(f"Config file {config_file} found but 'context' section missing")
            return ContextConfig()
            
        ctx_config = content["context"]
        return ContextConfig(
            enabled=ctx_config.get("enabled", True),
            file_patterns=ctx_config.get("file_patterns", ContextConfig.file_patterns.default_factory()),
            ignore_patterns=ctx_config.get("ignore_patterns", ContextConfig.ignore_patterns.default_factory()),
            max_results=ctx_config.get("max_results", 5),
            staleness_threshold=ctx_config.get("staleness_threshold", 3600),
        )
    except yaml.YAMLError as e:
        logger.warning(f"Failed to parse config file {config_file}: {e}. Using defaults.")
        return ContextConfig()
    except Exception as e:
        logger.warning(f"Unexpected error loading config from {config_file}: {e}. Using defaults.")
        return ContextConfig()
