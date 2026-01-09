# AI Context Tracking Workflow

## Overview

This document describes the automated git workflow that enables Claude Code to autonomously track project changes, understand context, and support safe rollbacks.

**Goal**: Enable AI to rapidly understand project state by tracking all changes in structured JSON logs.

## Architecture

### Directory Structure

```
.claude/
  context/
    commit_log.json      # Structured commit history with AI summaries
    branch_history.json  # Branch creation/merge tracking
    rollback_points.json # Safe rollback checkpoints
  commands/
    new-branch.md        # /new-branch slash command
    merge-branch.md      # /merge-branch slash command
    show-context.md      # /show-context slash command
    rollback.md          # /rollback slash command

scripts/
  auto_feature_branch.sh # Automated branch creation
  auto_merge_to_main.sh  # Automated merge with safety checks

.git/hooks/
  pre-commit             # Captures staged changes
  commit-msg             # Adds commit message to context
  post-commit            # Finalizes commit entry with hash
  post-merge             # Tracks merges and creates rollback points
```

### Git Hooks Flow

#### Pre-commit Hook
1. Captures staged files
2. Counts lines added/deleted
3. Extracts file types
4. Saves temporary JSON entry

#### Commit-msg Hook
1. Reads commit message
2. Combines with pre-commit data
3. Generates AI summary
4. Prepares final entry

#### Post-commit Hook
1. Gets actual commit hash
2. Updates entry with real hash
3. Appends to `commit_log.json`
4. Updates metadata (total commits, last updated)

#### Post-merge Hook
1. Detects source/target branches
2. Records merge in `branch_history.json`
3. Creates rollback point in `rollback_points.json`
4. Updates active branch metadata

## Workflow

### 1. Create Feature Branch

**Manual:**
```bash
./scripts/auto_feature_branch.sh feat new-feature "Description"
```

**Via Claude Code:**
```
/new-branch feat new-feature "Description"
```

**What happens:**
- Creates branch: `feat/new-feature`
- Updates `branch_history.json` with creation event
- Sets AI context to track this branch

### 2. Make Changes & Commit

```bash
# Make your changes
git add .
git commit -m "Implement new feature"
```

**What happens:**
- Pre-commit hook captures file changes
- Commit-msg hook adds message
- Post-commit hook finalizes entry in `commit_log.json`
- AI can now read structured change history

### 3. Merge to Main

**Manual:**
```bash
./scripts/auto_merge_to_main.sh
```

**Via Claude Code:**
```
/merge-branch
```

**What happens:**
- Runs tests (if available)
- Switches to main and pulls
- Merges with `--no-ff` (preserves history)
- Post-merge hook creates rollback point
- Updates branch status to "merged"
- Optionally deletes feature branch
- Optionally pushes to remote

### 4. View AI Context

**Via Claude Code:**
```
/show-context
```

This displays:
- Recent commits with AI summaries
- Branch creation/merge history
- Available rollback points

### 5. Rollback if Needed

**Via Claude Code:**
```
/rollback
```

This will:
- Show available rollback points
- Create backup branch before rollback
- Safely reset to selected checkpoint

## AI Context Format

### commit_log.json

```json
{
  "commits": [
    {
      "timestamp": "2026-01-09T12:00:00Z",
      "branch": "feat/ai-improvement",
      "files_changed": 3,
      "lines_added": 150,
      "lines_deleted": 20,
      "file_types": "py,html,js",
      "staged_files": ["app/services/ai_service.py", "..."],
      "commit_hash": "abc123...",
      "short_hash": "abc123",
      "commit_message": "Improve AI reply generation",
      "ai_summary": "Changed 3 files (+150 -20)"
    }
  ],
  "metadata": {
    "last_updated": "2026-01-09T12:00:00Z",
    "total_commits": 1,
    "ai_context_version": "1.0"
  }
}
```

### branch_history.json

```json
{
  "branches": [
    {
      "timestamp": "2026-01-09T12:00:00Z",
      "type": "branch_create",
      "branch_name": "feat/ai-improvement",
      "branch_type": "feat",
      "base_commit": "abc123...",
      "short_hash": "abc123",
      "description": "Improve AI reply generation logic",
      "status": "active"
    },
    {
      "timestamp": "2026-01-09T13:00:00Z",
      "type": "merge",
      "source_branch": "feat/ai-improvement",
      "target_branch": "main",
      "merge_commit": "def456...",
      "short_hash": "def456",
      "message": "Merge branch 'feat/ai-improvement' into main",
      "status": "merged"
    }
  ],
  "metadata": {
    "last_updated": "2026-01-09T13:00:00Z",
    "total_branches": 2,
    "active_branch": "main"
  }
}
```

### rollback_points.json

```json
{
  "rollback_points": [
    {
      "timestamp": "2026-01-09T13:00:00Z",
      "commit_hash": "def456...",
      "short_hash": "def456",
      "branch": "main",
      "description": "After merge: feat/ai-improvement → main",
      "can_revert_to": "ORIG_HEAD"
    }
  ],
  "metadata": {
    "last_updated": "2026-01-09T13:00:00Z",
    "total_points": 1,
    "description": "Safe points for reverting changes"
  }
}
```

## Branch Naming Convention

- **feat/** - New features
- **fix/** - Bug fixes
- **refactor/** - Code refactoring
- **docs/** - Documentation changes
- **test/** - Test additions/changes
- **chore/** - Maintenance tasks

## Benefits for AI

1. **Rapid Context Loading**: AI reads structured JSON instead of parsing git log
2. **Change Understanding**: Each commit has metadata (files, types, line counts)
3. **Branch Awareness**: AI knows which branches exist, their purpose, and status
4. **Safe Experimentation**: Rollback points allow AI to try changes safely
5. **History Preservation**: `--no-ff` merges keep branch history visible

## Best Practices

1. **Always use scripts** for branch operations to ensure AI context tracking
2. **Write descriptive commit messages** - they become AI summaries
3. **Create rollback points** before risky changes
4. **Use slash commands** in Claude Code for consistency
5. **Review context regularly** with `/show-context`

## Troubleshooting

### Hooks not running
```bash
# Ensure hooks are executable
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/commit-msg
chmod +x .git/hooks/post-commit
chmod +x .git/hooks/post-merge
```

### Context files corrupted
```bash
# Reset context files
echo '{"commits":[],"metadata":{"last_updated":"","total_commits":0,"ai_context_version":"1.0"}}' > .claude/context/commit_log.json
echo '{"branches":[],"metadata":{"last_updated":"","total_branches":0,"active_branch":"main"}}' > .claude/context/branch_history.json
echo '{"rollback_points":[],"metadata":{"last_updated":"","total_points":0,"description":"Safe points for reverting changes"}}' > .claude/context/rollback_points.json
```

### Scripts not found
```bash
# Ensure scripts are executable
chmod +x scripts/auto_feature_branch.sh
chmod +x scripts/auto_merge_to_main.sh
```

## Future Enhancements

1. **Auto-PR creation**: Extend merge script to create GitHub PRs
2. **AI-suggested commits**: AI analyzes diffs and suggests commit messages
3. **Conflict resolution**: AI helps resolve merge conflicts
4. **Performance tracking**: Log build times, test results in context
5. **Code review**: AI reviews changes before merge

## Integration with CLAUDE.md

This workflow complements the existing development policy:
- Still develop in dev mode first (`USE_MOCK_DATA=true`)
- Get user approval before production changes
- Now with fine-grained branch history for AI to track
- Easy rollback if production deployment fails

## Commands Quick Reference

| Command | Purpose |
|---------|---------|
| `/new-branch feat name "desc"` | Create feature branch |
| `/merge-branch` | Merge to main |
| `/show-context` | View AI tracking logs |
| `/rollback` | Revert to checkpoint |
| `./scripts/auto_feature_branch.sh` | Manual branch creation |
| `./scripts/auto_merge_to_main.sh` | Manual merge |
