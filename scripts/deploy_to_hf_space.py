"""
Deploy the app to a Hugging Face Space (Docker).

What it does:
  1. Creates the Space if it does not exist yet.
  2. Takes the last *committed* version of the code (uncommitted changes are not deployed).
  3. Adds the Space settings header to README.md (Hugging Face reads it to know
     this is a Docker app listening on port 8080).
  4. Uploads the files. Hugging Face then builds the Dockerfile and starts the app.

Before the first run, give the script a Hugging Face access token with write access,
either by adding it to .env as HF_TOKEN=... or by signing in once with:
    .venv\\Scripts\\huggingface-cli login

Usage:
    python scripts/deploy_to_hf_space.py <username>/<space-name> [--private]
"""

import argparse
import io
import subprocess
import tarfile
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import HfApi

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Lets HF_TOKEN be read from .env (huggingface_hub picks it up from the environment).
load_dotenv(PROJECT_ROOT / ".env")

SPACE_HEADER = """---
title: Call Quality Auditor
emoji: 🎧
colorFrom: blue
colorTo: green
sdk: docker
app_port: 8080
pinned: false
---

"""

# Not needed to run the app.
SKIP_PATTERNS = ["samples/*", "tests/*", "scripts/*", "cloudbuild.yaml", "pytest.ini", "data/uploads/*"]

# Folders that are fully replaced on every deploy, so deleted files do not linger on the Space.
REPLACED_FOLDERS = ["backend/*", "frontend/*", "data/*"]

REQUIRED_SECRETS = ["ADMIN_USERNAME", "ADMIN_PASSWORD", "FLASK_SECRET_KEY",
                    "GROQ_API_KEY", "PINECONE_API_KEY", "DATABASE_URL"]


def export_committed_code(destination: Path):
    """Write the files from the latest commit (HEAD) into `destination`."""
    archive = subprocess.run(["git", "archive", "--format=tar", "HEAD"],
                             cwd=PROJECT_ROOT, capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(destination, filter="data")


def add_space_header(readme: Path):
    readme.write_text(SPACE_HEADER + readme.read_text(encoding="utf-8"), encoding="utf-8")


def app_url(space_id: str) -> str:
    owner, name = space_id.split("/")
    subdomain = f"{owner}-{name}".lower().replace("_", "-").replace(".", "-")
    return f"https://{subdomain}.hf.space"


def main():
    parser = argparse.ArgumentParser(description="Deploy to a Hugging Face Space")
    parser.add_argument("space_id", help="e.g. your-username/call-quality-auditor")
    parser.add_argument("--private", action="store_true", help="only you can open the Space")
    args = parser.parse_args()

    api = HfApi()
    api.create_repo(args.space_id, repo_type="space", space_sdk="docker",
                    private=args.private, exist_ok=True)

    with tempfile.TemporaryDirectory() as staging:
        staging_path = Path(staging)
        export_committed_code(staging_path)
        add_space_header(staging_path / "README.md")

        print(f"Uploading to https://huggingface.co/spaces/{args.space_id} ...")
        api.upload_folder(
            folder_path=staging_path,
            repo_id=args.space_id,
            repo_type="space",
            ignore_patterns=SKIP_PATTERNS,
            delete_patterns=REPLACED_FOLDERS,
            commit_message="Deploy from GitHub repository",
        )

    print("\nUploaded. Hugging Face is now building the app (about 5 minutes).")
    print(f"  Build logs: https://huggingface.co/spaces/{args.space_id}?logs=build")
    print(f"  App:        {app_url(args.space_id)}")
    print(f"\nMake sure these secrets are set in the Space settings: {', '.join(REQUIRED_SECRETS)}")


if __name__ == "__main__":
    main()
