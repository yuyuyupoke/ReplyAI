---
description: Merge current feature branch to main with safety checks
---

Merge the current feature branch back to main using the auto_merge_to_main.sh script.

This will:
1. Check for uncommitted changes
2. Run tests if available
3. Switch to main and pull latest
4. Merge with --no-ff (preserves branch history)
5. Update AI context
6. Optionally delete the feature branch
7. Optionally push to remote

Please run: ./scripts/auto_merge_to_main.sh
