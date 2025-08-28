#!/usr/bin/env python3
"""
Run this to generate a new game and auto-commit it into the Website repo.
"""

import subprocess
from pathlib import Path
from datetime import datetime

from GameDevAI.src.create_game import publish_game   # <-- your module with publish_game()

# Adjust if needed
SITE_DIR = Path(__file__).parent.parent / "Website"


def git(cmd, cwd):
    """Run a git command in cwd and return stdout."""
    return subprocess.check_output(["git"] + cmd, cwd=cwd, text=True).strip()


def main():
    # 1. Prompt for the game idea
    prompt = input("Enter your game idea: ").strip()
    if not prompt:
        print("No prompt given. Exiting.")
        return

    # 2. Generate & publish game (to Website/)
    print("✨ Generating game...")
    summary = publish_game(prompt=prompt, site_dir=SITE_DIR)
    print("\n=== Game Summary ===\n")
    print(summary)
    print("\n====================\n")

    # 3. Git add/commit/push
    print("📦 Committing to git…")
    git(["add", "."], cwd=SITE_DIR)

    msg = f"Add game: {prompt[:40]} - {datetime.utcnow().isoformat(timespec='seconds')}Z"
    try:
        git(["commit", "-m", msg], cwd=SITE_DIR)
    except subprocess.CalledProcessError:
        print("⚠️ No changes to commit.")
        return

    print("🚀 Pushing to origin…")
    git(["push"], cwd=SITE_DIR)

    print("\n✅ Done! Your game should appear on GitHub Pages shortly.")


if __name__ == "__main__":
    main()