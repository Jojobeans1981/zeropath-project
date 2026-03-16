import logging
from pathlib import Path
from typing import Optional, Dict, List
import git

logger = logging.getLogger(__name__)

SKIP_DIRS = {
    ".git", "venv", "env", ".venv", "node_modules", "__pycache__",
    ".tox", ".eggs", "site-packages", ".mypy_cache", ".pytest_cache",
    "dist", "build", ".egg-info",
}


def clone_repo(url: str, dest: Path, github_token: Optional[str] = None) -> str:
    """Clone a git repo to dest directory (shallow). Returns commit SHA."""
    logger.info("[Scanner] Cloning %s to %s (authenticated: %s)", url, dest, bool(github_token))

    clone_url = url
    if github_token and "github.com" in url:
        clone_url = url.replace("https://", f"https://{github_token}@")

    repo = git.Repo.clone_from(
        clone_url,
        str(dest),
        depth=1,
        kill_after_timeout=120,
    )
    sha = repo.head.commit.hexsha
    logger.info("[Scanner] Cloned successfully, HEAD at %s", sha[:7])
    return sha


def discover_python_files(repo_path: Path) -> list[Path]:
    """Walk repo and return relative paths to all .py files, skipping irrelevant dirs."""
    py_files = []

    for path in repo_path.rglob("*.py"):
        # Check if any parent directory should be skipped
        parts = path.relative_to(repo_path).parts
        if any(part in SKIP_DIRS for part in parts):
            continue
        py_files.append(path.relative_to(repo_path))

    py_files.sort()
    logger.info("[Scanner] Discovered %d Python files", len(py_files))
    return py_files


LANGUAGE_CONFIG = {
    "python": {
        "extensions": [".py"],
        "skip_dirs": {"venv", "env", ".venv", "__pycache__", ".tox", ".eggs", "site-packages", ".mypy_cache", ".pytest_cache"},
    },
    "javascript": {
        "extensions": [".js", ".jsx", ".ts", ".tsx"],
        "skip_dirs": {"node_modules", "dist", "build", ".next", "coverage", "vendor", "bower_components"},
    },
}


def discover_source_files(repo_path: Path) -> Dict[str, List[Path]]:
    """Discover source files for all detected languages. Returns {language: [relative_paths]}."""
    result = {}
    for lang, config in LANGUAGE_CONFIG.items():
        files = []
        for ext in config["extensions"]:
            for path in repo_path.rglob(f"*{ext}"):
                parts = path.relative_to(repo_path).parts
                if any(part in config["skip_dirs"] or part in SKIP_DIRS for part in parts):
                    continue
                files.append(path.relative_to(repo_path))
        if files:
            files.sort()
            result[lang] = files
            logger.info("[Scanner] Discovered %d %s files", len(files), lang)
    return result
