"""Script to initialize GitHub labels from config."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.services.github_service import GitHubService
from src.agents.github_manager import GitHubManagerAgent


async def main():
    print("Setting up GitHub labels...")
    gh_service = GitHubService()
    gh_manager = GitHubManagerAgent(gh_service)
    await gh_manager.setup_labels()
    print("Done! Labels have been created/updated.")


if __name__ == "__main__":
    asyncio.run(main())
