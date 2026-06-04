#!/usr/bin/env bash
# =============================================================================
# CodeStudio Environment Health Check
#
# Usage:
#   bash scripts/check_codestudio_env.sh
#
# This script only RUNS CHECKS — it does NOT modify server state.
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass()  { echo -e "${GREEN}[PASS]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
info()  { echo -e "  $*"; }

PROJECT_DIR="$HOME/ai_study_platform"
VENV_PYTHON="$PROJECT_DIR/backend/.venv/bin/python3"
VENV_PIP="$PROJECT_DIR/backend/.venv/bin/pip"
STATIC_DIR="/var/www/ai_study_platform"

echo "=========================================="
echo " CodeStudio Environment Health Check"
echo " $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

# ── 1. Project directory ──
echo ""
echo "── 1. Project directory ──"
if [ -d "$PROJECT_DIR" ]; then
    pass "Project directory exists: $PROJECT_DIR"
    info "Git HEAD: $(cd "$PROJECT_DIR" && git rev-parse --short HEAD 2>/dev/null || echo 'N/A')"
else
    fail "Project directory not found: $PROJECT_DIR"
fi

# ── 2. Python venv ──
echo ""
echo "── 2. Python virtual environment ──"
if [ -x "$VENV_PYTHON" ]; then
    pass "Python venv exists: $VENV_PYTHON"
    info "Python version: $($VENV_PYTHON --version 2>&1)"
else
    fail "Python venv not found or not executable: $VENV_PYTHON"
fi

# ── 3. WebSocket dependencies ──
echo ""
echo "── 3. WebSocket dependencies ──"
WS_CHECK=$("$VENV_PYTHON" -c "
try:
    import websockets
    print('websockets', websockets.__version__)
except ImportError as e:
    print('MISSING: websockets —', e)
try:
    import asyncio
    print('asyncio ok')
except ImportError as e:
    print('MISSING: asyncio —', e)
" 2>&1)
if echo "$WS_CHECK" | grep -q "MISSING"; then
    fail "WebSocket dependencies missing"
    info "Run: $VENV_PIP install -r $PROJECT_DIR/backend/requirements.txt"
    info "$WS_CHECK"
else
    pass "WebSocket dependencies OK"
    info "$WS_CHECK"
fi

# ── 4. Docker ──
echo ""
echo "── 4. Docker ──"
if command -v docker &>/dev/null; then
    pass "Docker CLI available: $(docker --version 2>&1)"
    if docker info &>/dev/null; then
        pass "Docker daemon running"
        info "User groups: $(groups)"
    else
        fail "Docker daemon not accessible — check permissions"
        info "Run: sudo usermod -aG docker \$USER && re-login"
    fi
else
    fail "Docker not found — C run/diagnosis will not work"
fi

# ── 5. Docker images ──
echo ""
echo "── 5. Docker images ──"
check_image() {
    local image="$1"
    if docker image inspect "$image" &>/dev/null; then
        pass "Image available: $image"
    else
        fail "Image missing: $image"
        info "Run: docker pull $image"
    fi
}
check_image "gcc:13"
check_image "python:3.11-slim"

# ── 6. systemd service ──
echo ""
echo "── 6. systemd ai-backend service ──"
if systemctl is-active --quiet ai-backend 2>/dev/null; then
    pass "ai-backend service is active"
else
    fail "ai-backend service is NOT active"
    info "Run: sudo systemctl restart ai-backend"
    info "Check: sudo journalctl -u ai-backend -n 50 --no-pager"
fi

# ── 7. Nginx ──
echo ""
echo "── 7. Nginx ──"
if sudo nginx -t 2>&1; then
    pass "Nginx config is valid"
else
    fail "Nginx config has errors"
fi

# ── 8. Nginx WebSocket Upgrade ──
echo ""
echo "── 8. Nginx WebSocket Upgrade ──"
NGINX_CFG=$(sudo nginx -T 2>/dev/null || true)
if echo "$NGINX_CFG" | grep -q "interactive-run"; then
    if echo "$NGINX_CFG" | grep -q "Upgrade.*http_upgrade"; then
        pass "WebSocket Upgrade headers configured for interactive-run"
    else
        warn "interactive-run location exists but missing Upgrade headers"
    fi
else
    fail "No interactive-run location found in Nginx config"
    info "Copy template: deploy/nginx-ai-study-platform.conf.example"
fi

# ── 9. Static files ──
echo ""
echo "── 9. Static files ──"
if [ -f "$STATIC_DIR/index.html" ]; then
    pass "Static files exist: $STATIC_DIR"
    info "CodeStudio bundle: $(ls "$STATIC_DIR/assets/CodeStudio-"*.js 2>/dev/null | head -1 || echo 'N/A')"
else
    fail "Static files missing: $STATIC_DIR"
    info "Run: cd $PROJECT_DIR/frontend && npm ci && npm run build"
    info "Then: sudo rsync -a --delete dist/ $STATIC_DIR/"
fi

# ── 10. HTTP reachable ──
echo ""
echo "── 10. HTTP endpoint ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1/ 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    pass "HTTP endpoint reachable (200 OK)"
else
    fail "HTTP endpoint returned $HTTP_CODE"
fi

# ── Summary ──
echo ""
echo "=========================================="
echo " Health check complete."
echo " Review any [FAIL] items above and follow"
echo " the docs/deploy-codestudio.md guide."
echo "=========================================="
