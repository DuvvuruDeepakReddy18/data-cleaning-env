"""
Push data_cleaning_env v2.0 project files to GitHub repository.
Uses GitHub API (no git installation needed).

Run: python push_to_github.py
"""

import os
import sys
import base64

def main():
    try:
        import requests
    except ImportError:
        os.system(f"{sys.executable} -m pip install requests")
        import requests

    # ── Configuration ──
    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
    REPO_OWNER = "DuvvuruDeepakReddy18"
    REPO_NAME = "data-cleaning-env"

    if not GITHUB_TOKEN:
        print("=" * 60)
        print("  GitHub Personal Access Token Required")
        print("=" * 60)
        print()
        print("  1. Go to: https://github.com/settings/tokens/new")
        print("  2. Note: 'data-cleaning-env v2.0 upload'")
        print("  3. Expiration: 7 days")
        print("  4. Check ONLY: 'repo' (Full control)")
        print("  5. Click 'Generate token'")
        print("  6. Copy the token (starts with 'ghp_')")
        print()
        GITHUB_TOKEN = input("  Paste your token here: ").strip()
        if not GITHUB_TOKEN:
            print("  ERROR: No token provided.")
            sys.exit(1)

    # Project directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.join(script_dir, "data_cleaning_env_project", "data_cleaning_env")

    if not os.path.exists(project_dir):
        print(f"ERROR: Project directory not found at: {project_dir}")
        sys.exit(1)

    print(f"\nProject directory: {project_dir}")
    print(f"Pushing to: https://github.com/{REPO_OWNER}/{REPO_NAME}")
    print()

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    # Specific files to upload (explicit list for reliability)
    files_to_upload = []

    file_list = [
        "inference.py",
        "openenv.yaml",
        "Dockerfile",
        "pyproject.toml",
        "requirements.txt",
        "README.md",
        "data_cleaning_env/__init__.py",
        "data_cleaning_env/client.py",
        "data_cleaning_env/models.py",
        "data_cleaning_env/server/__init__.py",
        "data_cleaning_env/server/app.py",
        "data_cleaning_env/server/environment.py",
        "data_cleaning_env/tasks/__init__.py",
        "data_cleaning_env/tasks/task_definitions.py",
    ]

    for rel_path in file_list:
        filepath = os.path.join(project_dir, rel_path.replace("/", os.sep))
        if os.path.exists(filepath):
            files_to_upload.append((filepath, rel_path))
        else:
            print(f"  WARNING: File not found: {rel_path}")

    print(f"Found {len(files_to_upload)} files to upload:")
    for _, gh_path in files_to_upload:
        print(f"  {gh_path}")
    print()

    # Upload each file
    api_base = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents"
    success_count = 0
    error_count = 0

    for filepath, gh_path in files_to_upload:
        print(f"  Uploading: {gh_path} ... ", end="", flush=True)

        with open(filepath, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")

        check_resp = requests.get(f"{api_base}/{gh_path}", headers=headers)

        payload = {
            "message": f"v2.0: Update {gh_path} - batch actions, expert task, improved rewards",
            "content": content,
        }

        if check_resp.status_code == 200:
            payload["sha"] = check_resp.json()["sha"]

        resp = requests.put(f"{api_base}/{gh_path}", headers=headers, json=payload)

        if resp.status_code in [200, 201]:
            print("OK")
            success_count += 1
        else:
            print(f"FAILED ({resp.status_code})")
            try:
                print(f"    Error: {resp.json().get('message', 'Unknown error')}")
            except:
                pass
            error_count += 1

    print()
    print("=" * 60)
    if error_count == 0:
        print(f"  SUCCESS! All {success_count} files uploaded to GitHub.")
    else:
        print(f"  Uploaded: {success_count}, Failed: {error_count}")
    print(f"  Repo: https://github.com/{REPO_OWNER}/{REPO_NAME}")
    print("=" * 60)
    print()
    print("NEXT STEPS:")
    print(f"  1. Check repo: https://github.com/{REPO_OWNER}/{REPO_NAME}")
    print("  2. Wait for HuggingFace Space to auto-rebuild (~2-5 min)")
    print("  3. Once rebuilt, go to hackathon dashboard and click 'Update submission'")
    print("  4. Verify Phase 1 and Phase 2 checks pass")


if __name__ == "__main__":
    main()
