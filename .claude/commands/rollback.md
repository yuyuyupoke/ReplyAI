---
description: Rollback to a previous safe checkpoint
---

Rollback to a previous safe checkpoint from the rollback_points.json.

This command will:
1. Show available rollback points
2. Allow selection of a checkpoint
3. Create a backup branch before rollback
4. Reset to the selected commit

Usage: /rollback

First, please show the contents of .claude/context/rollback_points.json to list available checkpoints, then help the user select and execute the rollback safely.
