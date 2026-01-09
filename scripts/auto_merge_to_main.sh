#!/bin/bash
# Auto-merge feature branch to main with safety checks

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)

# Check if on main
if [ "$CURRENT_BRANCH" = "main" ]; then
    echo -e "${RED}✗ Already on main branch. Nothing to merge.${NC}"
    exit 1
fi

# Check for uncommitted changes
if ! git diff-index --quiet HEAD --; then
    echo -e "${RED}✗ You have uncommitted changes. Please commit or stash them first.${NC}"
    exit 1
fi

echo -e "${BLUE}→ Current branch: $CURRENT_BRANCH${NC}"

# Get branch info
BRANCH_TYPE=$(echo $CURRENT_BRANCH | cut -d'/' -f1)
BRANCH_NAME=$(echo $CURRENT_BRANCH | cut -d'/' -f2-)

# Optional: Run tests if test command exists
if [ -f "run_tests.sh" ]; then
    echo -e "${BLUE}→ Running tests...${NC}"
    if ./run_tests.sh; then
        echo -e "${GREEN}✓ Tests passed${NC}"
    else
        echo -e "${RED}✗ Tests failed. Merge aborted.${NC}"
        exit 1
    fi
fi

# Switch to main and update
echo -e "${BLUE}→ Switching to main...${NC}"
git checkout main

echo -e "${BLUE}→ Pulling latest changes...${NC}"
git pull origin main --quiet || true

# Merge feature branch
echo -e "${BLUE}→ Merging $CURRENT_BRANCH into main...${NC}"
if git merge --no-ff $CURRENT_BRANCH -m "Merge branch '$CURRENT_BRANCH' into main

[$BRANCH_TYPE] $BRANCH_NAME
"; then
    echo -e "${GREEN}✓ Merge successful${NC}"
else
    echo -e "${RED}✗ Merge failed. Please resolve conflicts manually.${NC}"
    exit 1
fi

# Update branch status in AI context
CONTEXT_DIR=".claude/context"
BRANCH_HISTORY="$CONTEXT_DIR/branch_history.json"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

python3 -c "
import json
import os

branch_history_path = '$BRANCH_HISTORY'

if os.path.exists(branch_history_path):
    with open(branch_history_path, 'r') as f:
        history = json.load(f)

    # Find the branch entry and mark as merged
    for branch in history['branches']:
        if branch.get('branch_name') == '$CURRENT_BRANCH' and branch.get('type') == 'branch_create':
            branch['status'] = 'merged'
            branch['merged_at'] = '$TIMESTAMP'
            break

    history['metadata']['active_branch'] = 'main'

    with open(branch_history_path, 'w') as f:
        json.dump(history, f, indent=2)
"

# Ask if user wants to delete the feature branch
echo ""
echo -e "${YELLOW}Delete feature branch '$CURRENT_BRANCH'? (y/N)${NC}"
read -r response

if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    git branch -d $CURRENT_BRANCH
    echo -e "${GREEN}✓ Branch deleted: $CURRENT_BRANCH${NC}"
else
    echo -e "${BLUE}→ Branch kept: $CURRENT_BRANCH${NC}"
fi

echo ""
echo -e "${GREEN}✓ Merge complete!${NC}"
echo -e "${BLUE}Current branch: main${NC}"

# Show option to push
echo ""
echo -e "${YELLOW}Push to remote? (y/N)${NC}"
read -r push_response

if [[ "$push_response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo -e "${BLUE}→ Pushing to origin/main...${NC}"
    git push origin main
    echo -e "${GREEN}✓ Pushed to remote${NC}"
fi

exit 0
