"""Configuration for auto-fix module."""

import yaml
import logging
from pathlib import Path
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class StrategyConfig:
    """Configuration for a specific fix strategy."""
    enabled: bool = True
    params: dict = field(default_factory=dict)


@dataclass
class AutoFixConfig:
    """Main configuration for auto-fix."""
    enabled: bool = True
    max_attempts: int = 3
    backup_retention_days: int = 7
    
    # Safety settings
    require_clean_git: bool = True
    max_file_size_kb: int = 500
    timeout_seconds: int = 300
    
    # Strategies
    strategies: dict[str, StrategyConfig] = field(default_factory=lambda: {
        "formatting": StrategyConfig(enabled=True),
        "imports": StrategyConfig(enabled=True),
        "types": StrategyConfig(enabled=True),
    })


def load_config(project_root: Path) -> AutoFixConfig:
    """Load configuration from .bmad/config.yaml or auto_fix_config.yaml.
    
    Args:
        project_root: Project root directory
        
    Returns:
        AutoFixConfig object (with defaults if file missing)
    """
    # Check for unified config first
    config_file = project_root / ".bmad" / "config.yaml"
    
    if not config_file.exists():
        # Check for legacy/specific config
        config_file = project_root / ".bmad" / "auto_fix_config.yaml"
    
    if not config_file.exists():
        return AutoFixConfig()
        
    try:
        content = yaml.safe_load(config_file.read_text())
        if not content:
            return AutoFixConfig()
            
        # Extract section
        data = content.get("auto_fix", content)
        
        config = AutoFixConfig(
            enabled=data.get("enabled", True),
            max_attempts=data.get("max_attempts", 3),
            backup_retention_days=data.get("backup_retention_days", 7),
            require_clean_git=data.get("safety", {}).get("require_clean_git", True),
            max_file_size_kb=data.get("safety", {}).get("max_file_size_kb", 500),
            timeout_seconds=data.get("safety", {}).get("timeout_seconds", 300),
        )
        
        # Load strategies
        strat_data = data.get("strategies", {})
        for name, settings in strat_data.items():
            if isinstance(settings, dict):
                config.strategies[name] = StrategyConfig(
                    enabled=settings.get("enabled", True),
                    params=settings
                )
                
        return config
        
    except Exception as e:
        logger.warning(f"Failed to load auto-fix config from {config_file}: {e}")
        return AutoFixConfig()
