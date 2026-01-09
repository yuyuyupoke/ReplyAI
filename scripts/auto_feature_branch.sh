#!/bin/bash
# Auto-create feature branch with AI context tracking

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Usage info
usage() {
    echo "Usage: $0 <branch-type> <branch-name> [description]"
    echo ""
    echo "Branch types:"
    echo "  feat     - New feature"
    echo "  fix      - Bug fix"
    echo "  refactor - Code refactoring"
    echo "  docs     - Documentation"
    echo "  test     - Testing"
    echo "  chore    - Maintenance"
    echo ""
    echo "Example: $0 feat ai-reply-improvement 'Improve AI reply generation logic'"
    exit 1
}

# Check arguments
if [ $# -lt 2 ]; then
    usage
fi

BRANCH_TYPE=$1
BRANCH_NAME=$2
DESCRIPTION=${3:-""}

# Validate branch type
case $BRANCH_TYPE in
    feat|fix|refactor|docs|test|chore)
        ;;
    *)
        echo -e "${YELLOW}⚠ Invalid branch type: $BRANCH_TYPE${NC}"
        usage
        ;;
esac

# Create full branch name
FULL_BRANCH_NAME="${BRANCH_TYPE}/${BRANCH_NAME}"

# Check if branch already exists
if git show-ref --quiet refs/heads/$FULL_BRANCH_NAME; then
    echo -e "${YELLOW}⚠ Branch $FULL_BRANCH_NAME already exists${NC}"
    exit 1
fi

# Ensure we're on main and up to date
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
    echo -e "${BLUE}→ Switching to main branch...${NC}"
    git checkout main
fi

echo -e "${BLUE}→ Pulling latest changes...${NC}"
git pull origin main --quiet || true

# Create and checkout new branch
echo -e "${BLUE}→ Creating branch: $FULL_BRANCH_NAME${NC}"
git checkout -b $FULL_BRANCH_NAME

# Update AI context
CONTEXT_DIR=".claude/context"
BRANCH_HISTORY="$CONTEXT_DIR/branch_history.json"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
COMMIT_HASH=$(git rev-parse HEAD)
SHORT_HASH=$(git rev-parse --short HEAD)

python3 -c "
import json
import os

branch_history_path = '$BRANCH_HISTORY'

if os.path.exists(branch_history_path):
    with open(branch_history_path, 'r') as f:
        history = json.load(f)
else:
    history = {'branches': [], 'metadata': {'last_updated': '', 'total_branches': 0, 'active_branch': 'main'}}

branch_entry = {
    'timestamp': '$TIMESTAMP',
    'type': 'branch_create',
    'branch_name': '$FULL_BRANCH_NAME',
    'branch_type': '$BRANCH_TYPE',
    'base_commit': '$COMMIT_HASH',
    'short_hash': '$SHORT_HASH',
    'description': '''$DESCRIPTION''',
    'status': 'active'
}

history['branches'].insert(0, branch_entry)
history['metadata']['last_updated'] = '$TIMESTAMP'
history['metadata']['total_branches'] = len(history['branches'])
history['metadata']['active_branch'] = '$FULL_BRANCH_NAME'

with open(branch_history_path, 'w') as f:
    json.dump(history, f, indent=2)
"

echo -e "${GREEN}✓ Branch created: $FULL_BRANCH_NAME${NC}"
echo -e "${GREEN}✓ AI context updated${NC}"

if [ -n "$DESCRIPTION" ]; then
    echo -e "${BLUE}Description: $DESCRIPTION${NC}"
fi

echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Make your changes"
echo "  2. Commit with: git commit -m 'your message'"
echo "  3. Merge with: ./scripts/auto_merge_to_main.sh"

exit 0
