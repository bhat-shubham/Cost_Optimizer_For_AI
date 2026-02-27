"""
Dev bootstrap script — create a project and API key for local development.

Usage:
    python -m scripts.bootstrap_dev

This will:
  1. Create a new project named "Dev Project"
  2. Generate an API key
  3. Print the raw key ONCE (it is never stored)

The raw key is shown exactly once — copy it immediately.
"""

import asyncio
import sys

# Ensure the project root is on the path
sys.path.insert(0, ".")

from app.core.database import async_session_factory, engine
from app.models.project import Project
from app.models.api_key import APIKey
from app.auth.hashing import generate_api_key


async def main() -> None:
    project_name = "Dev Project"

    async with async_session_factory() as session:
        # ── Create project ──────────────────────────────────
        project = Project(name=project_name)
        session.add(project)
        await session.flush()  # get project.id

        # ── Generate API key ────────────────────────────────
        raw_key, key_hash = generate_api_key()

        api_key = APIKey(
            project_id=project.id,
            key_hash=key_hash,
            prefix=raw_key[:12],
        )
        session.add(api_key)
        await session.commit()

    # ── Print results ───────────────────────────────────────
    print()
    print("=" * 60)
    print("  Dev Bootstrap Complete")
    print("=" * 60)
    print()
    print(f"  Project:    {project.name}")
    print(f"  Project ID: {project.id}")
    print()
    print(f"  API Key:    {raw_key}")
    print()
    print("  ⚠  Copy this key now — it will NEVER be shown again.")
    print("=" * 60)
    print()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
