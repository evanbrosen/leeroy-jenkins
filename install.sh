#!/bin/bash
# leeroy-jenkins install script
# Symlinks the skill and agents into ~/.claude/ so edits to the repo take effect immediately.

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMANDS_DIR="$HOME/.claude/commands"
AGENTS_DIR="$HOME/.claude/agents"

echo "Installing leeroy-jenkins..."
echo "Repo: $REPO_DIR"

# Create target dirs if they don't exist
mkdir -p "$COMMANDS_DIR"
mkdir -p "$AGENTS_DIR"

# Symlink main skill
ln -sf "$REPO_DIR/leeroy-jenkins.md" "$COMMANDS_DIR/leeroy-jenkins.md"
echo "  ✓ Linked leeroy-jenkins.md → $COMMANDS_DIR/leeroy-jenkins.md"

# Remove old prep-demo skill if present
if [ -f "$COMMANDS_DIR/prep-demo.md" ]; then
  rm "$COMMANDS_DIR/prep-demo.md"
  echo "  ✓ Removed old prep-demo.md from $COMMANDS_DIR"
fi

# Symlink agents
for agent_file in "$REPO_DIR/agents/"*.md; do
  agent_name="$(basename "$agent_file")"
  ln -sf "$agent_file" "$AGENTS_DIR/$agent_name"
  echo "  ✓ Linked $agent_name → $AGENTS_DIR/$agent_name"
done

echo ""
echo "Done. /leeroy-jenkins and /leeroy-teardown are ready."
echo ""
echo "Next step: update config/users.json with your org's SF usernames and IDs."
echo "  File: $REPO_DIR/config/users.json"
