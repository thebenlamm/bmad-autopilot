#!/bin/bash
# BMAD Autopilot Setup - Install dependencies and verify configuration
# Usage: bmad-setup

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}BMAD Autopilot Setup${NC}"
echo ""

# Track if anything failed
SETUP_OK=true

# Check and install coreutils (for gtimeout on macOS)
echo -n "Checking timeout command... "
if command -v gtimeout &> /dev/null; then
    echo -e "${GREEN}✓ gtimeout${NC}"
elif command -v timeout &> /dev/null; then
    echo -e "${GREEN}✓ timeout${NC}"
else
    echo -e "${YELLOW}not found${NC}"
    if command -v brew &> /dev/null; then
        echo "  Installing coreutils..."
        brew install coreutils
    else
        echo -e "${RED}  Please install coreutils: brew install coreutils${NC}"
        SETUP_OK=false
    fi
fi

# Check and install yq
echo -n "Checking yq... "
if command -v yq &> /dev/null; then
    echo -e "${GREEN}✓ $(yq --version | head -1)${NC}"
else
    echo -e "${YELLOW}not found${NC}"
    if command -v brew &> /dev/null; then
        echo "  Installing yq..."
        brew install yq
    else
        echo -e "${RED}  Please install yq: https://github.com/mikefarah/yq${NC}"
        SETUP_OK=false
    fi
fi

# Check llm CLI
echo -n "Checking llm CLI... "
if command -v llm &> /dev/null; then
    echo -e "${GREEN}✓ $(llm --version 2>/dev/null | head -1 || echo "installed")${NC}"
else
    echo -e "${YELLOW}not found${NC}"
    echo "  Installing llm..."
    pip install llm || {
        echo -e "${RED}  Failed to install llm. Try: pip install llm${NC}"
        SETUP_OK=false
    }
fi

# Check llm-anthropic plugin
echo -n "Checking llm-anthropic plugin... "
if command -v llm &> /dev/null && llm plugins 2>/dev/null | grep -q "llm-anthropic"; then
    echo -e "${GREEN}✓ installed${NC}"
else
    echo -e "${YELLOW}not found${NC}"
    if command -v llm &> /dev/null; then
        echo "  Installing llm-anthropic..."
        llm install llm-anthropic || {
            echo -e "${RED}  Failed to install. Try: llm install llm-anthropic${NC}"
            SETUP_OK=false
        }
    fi
fi

# Check llm-gemini plugin
echo -n "Checking llm-gemini plugin... "
if command -v llm &> /dev/null && llm plugins 2>/dev/null | grep -q "llm-gemini"; then
    echo -e "${GREEN}✓ installed${NC}"
else
    echo -e "${YELLOW}not found${NC}"
    if command -v llm &> /dev/null; then
        echo "  Installing llm-gemini..."
        llm install llm-gemini || {
            echo -e "${RED}  Failed to install. Try: llm install llm-gemini${NC}"
            SETUP_OK=false
        }
    fi
fi

# Check tmux (optional)
echo -n "Checking tmux... "
if command -v tmux &> /dev/null; then
    echo -e "${GREEN}✓ installed${NC}"
else
    echo -e "${YELLOW}not installed (optional, for --tmux mode)${NC}"
fi

# Check aider (optional)
echo -n "Checking aider... "
if command -v aider &> /dev/null; then
    echo -e "${GREEN}✓ installed${NC}"
else
    echo -e "${YELLOW}not installed (optional)${NC}"
    echo "  → For automated development: pip install aider-chat"
fi

# Check claude CLI (optional)
echo -n "Checking claude CLI... "
if command -v claude &> /dev/null; then
    echo -e "${GREEN}✓ installed${NC}"
else
    echo -e "${YELLOW}not installed (optional)${NC}"
    echo "  → Alternative to aider: https://claude.ai/code"
fi

# Verify API keys
echo ""
echo -e "${BLUE}API Keys${NC}"

echo -n "  Anthropic... "
if [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
    echo -e "${GREEN}✓ ANTHROPIC_API_KEY set${NC}"
elif command -v llm &> /dev/null && llm keys get anthropic &>/dev/null; then
    echo -e "${GREEN}✓ configured in llm${NC}"
else
    echo -e "${YELLOW}⚠ not configured${NC}"
    echo "    Set with: llm keys set anthropic"
fi

echo -n "  Gemini... "
if [[ -n "${GEMINI_API_KEY:-}" ]]; then
    echo -e "${GREEN}✓ GEMINI_API_KEY set${NC}"
elif command -v llm &> /dev/null && llm keys get gemini &>/dev/null; then
    echo -e "${GREEN}✓ configured in llm${NC}"
else
    echo -e "${YELLOW}⚠ not configured (optional)${NC}"
    echo "    Set with: llm keys set gemini"
fi

# Summary
echo ""
if $SETUP_OK; then
    echo -e "${GREEN}✅ Setup complete!${NC}"
    echo ""
    echo "Quick start:"
    echo "  bmad-phase status                    # Check sprint status"
    echo "  bmad-phase next                      # See next stories"
    echo "  bmad-autopilot --project ~/myproj    # Run full pipeline"
else
    echo -e "${RED}⚠ Some dependencies missing. Please install them and re-run.${NC}"
    exit 1
fi
