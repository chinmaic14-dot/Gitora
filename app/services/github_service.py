# ============================================================
# GITORA GITHUB SERVICE
# GitHub REST API integration
# ============================================================

import os
import base64
import requests

from urllib.parse import urlparse

from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

GITHUB_API = "https://api.github.com"

GITHUB_TOKEN = os.getenv(
    "GITHUB_TOKEN",
    ""
).strip()


GITHUB_TIMEOUT = int(
    os.getenv(
        "GITHUB_TIMEOUT",
        "30"
    )
)


# ============================================================
# GITHUB HEADERS
# ============================================================

HEADERS = {
    "Accept":
        "application/vnd.github+json",

    "X-GitHub-Api-Version":
        "2022-11-28",

    "User-Agent":
        "Gitora-AI-Repository-Analyzer"
}


if GITHUB_TOKEN:

    HEADERS["Authorization"] = (
        f"Bearer {GITHUB_TOKEN}"
    )


# ============================================================
# INTERNAL REQUEST HELPER
# ============================================================

def github_get(
    api_url,
    timeout=None
):
    """
    Perform a GET request to the GitHub REST API.

    Returns:
        tuple:
            (success, response_data)
    """

    if timeout is None:
        timeout = GITHUB_TIMEOUT

    try:

        response = requests.get(
            api_url,
            headers=HEADERS,
            timeout=timeout
        )

    except requests.exceptions.Timeout as error:

        raise RuntimeError(
            "GitHub API request timed out. "
            "Please try again."
        ) from error

    except requests.exceptions.ConnectionError as error:

        raise RuntimeError(
            "Unable to connect to GitHub. "
            "Please check your internet connection."
        ) from error

    except requests.exceptions.RequestException as error:

        raise RuntimeError(
            "GitHub API request failed."
        ) from error


    # ========================================================
    # SUCCESS
    # ========================================================

    if response.status_code == 200:

        try:
            return True, response.json()

        except ValueError as error:

            raise RuntimeError(
                "GitHub returned an invalid response."
            ) from error


    # ========================================================
    # RATE LIMIT
    # ========================================================

    if response.status_code == 403:

        remaining = response.headers.get(
            "X-RateLimit-Remaining"
        )

        if remaining == "0":

            raise RuntimeError(
                "GitHub API rate limit exceeded. "
                "Please add a valid GITHUB_TOKEN "
                "or wait before trying again."
            )

        raise RuntimeError(
            "GitHub denied the API request."
        )


    # ========================================================
    # NOT FOUND
    # ========================================================

    if response.status_code == 404:

        raise RuntimeError(
            "GitHub repository or file was not found. "
            "Please check the repository URL and make "
            "sure the repository is accessible."
        )


    # ========================================================
    # UNAUTHORIZED
    # ========================================================

    if response.status_code == 401:

        raise RuntimeError(
            "GitHub authentication failed. "
            "Please check your GITHUB_TOKEN."
        )


    # ========================================================
    # OTHER ERRORS
    # ========================================================

    try:

        error_data = response.json()

        message = error_data.get(
            "message",
            "Unknown GitHub API error."
        )

    except Exception:

        message = (
            response.text[:300]
            or "Unknown GitHub API error."
        )


    raise RuntimeError(
        f"GitHub API error "
        f"({response.status_code}): "
        f"{message}"
    )


# ============================================================
# PARSE GITHUB URL
# ============================================================

def parse_github_url(
    repo_url
):
    """
    Convert GitHub repository URL into:
        owner, repository

    Supports:

        https://github.com/user/repo
        https://github.com/user/repo.git
        github.com/user/repo
        user/repo
    """

    value = str(
        repo_url or ""
    ).strip()

    if not value:

        raise ValueError(
            "GitHub repository URL is empty."
        )


    # --------------------------------------------------------
    # Remove trailing slash
    # --------------------------------------------------------

    value = value.rstrip("/")


    # --------------------------------------------------------
    # Remove .git
    # --------------------------------------------------------

    if value.endswith(".git"):

        value = value[:-4]


    # --------------------------------------------------------
    # Full URL
    # --------------------------------------------------------

    if (
        value.startswith("https://")
        or value.startswith("http://")
    ):

        parsed = urlparse(
            value
        )

        hostname = (
            parsed.netloc
            .lower()
            .split(":")[0]
        )

        if hostname != "github.com":

            raise ValueError(
                "Please provide a valid github.com repository URL."
            )

        parts = [
            part
            for part in parsed.path.split("/")
            if part
        ]

    else:

        # ----------------------------------------------------
        # github.com/user/repo
        # ----------------------------------------------------

        if value.startswith(
            "github.com/"
        ):

            value = value[
                len("github.com/"):
            ]

        parts = [
            part
            for part in value.split("/")
            if part
        ]


    # --------------------------------------------------------
    # Validate
    # --------------------------------------------------------

    if len(parts) < 2:

        raise ValueError(
            "Invalid GitHub repository. "
            "Use owner/repository."
        )


    owner = parts[0].strip()

    repository = parts[1].strip()


    if not owner or not repository:

        raise ValueError(
            "Invalid GitHub repository."
        )


    return owner, repository


# ============================================================
# GET REPOSITORY INFORMATION
# ============================================================

def get_repository_info(
    repo_url
):
    """
    Get basic repository metadata.
    """

    owner, repository = parse_github_url(
        repo_url
    )


    api_url = (
        f"{GITHUB_API}/repos/"
        f"{owner}/{repository}"
    )


    _, data = github_get(
        api_url
    )


    return {
        "name":
            data.get(
                "name",
                repository
            ),

        "full_name":
            data.get(
                "full_name",
                f"{owner}/{repository}"
            ),

        "description":
            data.get(
                "description"
            )
            or "No description provided.",

        "language":
            data.get(
                "language"
            )
            or "Not detected",

        "stars":
            data.get(
                "stargazers_count",
                0
            ),

        "forks":
            data.get(
                "forks_count",
                0
            ),

        "open_issues":
            data.get(
                "open_issues_count",
                0
            ),

        "default_branch":
            data.get(
                "default_branch"
            )
            or "main",

        "owner":
            owner,

        "repo":
            repository,

        "url":
            data.get(
                "html_url",
                f"https://github.com/"
                f"{owner}/{repository}"
            )
    }


# ============================================================
# GET REPOSITORY FILES
# ============================================================

def get_repository_files(
    owner,
    repo,
    branch
):
    """
    Get the complete recursive file tree
    of a GitHub repository.
    """

    if not owner or not repo:

        raise ValueError(
            "GitHub owner and repository are required."
        )


    branch = (
        branch
        or "main"
    )


    api_url = (
        f"{GITHUB_API}/repos/"
        f"{owner}/{repo}/git/trees/"
        f"{branch}?recursive=1"
    )


    _, data = github_get(
        api_url,
        timeout=GITHUB_TIMEOUT
    )


    tree = data.get(
        "tree",
        []
    )


    files = []


    for item in tree:

        if item.get("type") != "blob":
            continue


        path = item.get(
            "path",
            ""
        ).strip()


        if not path:
            continue


        files.append({
            "path": path,

            "type": "file",

            "sha":
                item.get(
                    "sha",
                    ""
                ),

            "size":
                item.get(
                    "size",
                    0
                ),

            "url":
                item.get(
                    "url",
                    ""
                ),

            "categories":
                categorize_file(path)
        })


    files.sort(
        key=lambda item:
            item["path"].lower()
    )


    return files


# ============================================================
# GET FILE CONTENT
# ============================================================

def get_file_content(
    owner,
    repo,
    file_path,
    branch
):
    """
    Retrieve and decode a single text file
    from GitHub.
    """

    if not owner or not repo:

        raise ValueError(
            "GitHub owner and repository are required."
        )


    if not file_path:

        raise ValueError(
            "File path is required."
        )


    branch = (
        branch
        or "main"
    )


    api_url = (
        f"{GITHUB_API}/repos/"
        f"{owner}/{repo}/contents/"
        f"{file_path}"
        f"?ref={branch}"
    )


    try:

        _, data = github_get(
            api_url
        )

    except RuntimeError:

        # ----------------------------------------------------
        # Let the caller decide how to handle missing files.
        # ----------------------------------------------------

        return None


    if not isinstance(
        data,
        dict
    ):

        return None


    # ========================================================
    # GITHUB DIRECTORY RESPONSE
    # ========================================================

    if data.get("type") != "file":

        return None


    encoded_content = data.get(
        "content"
    )


    if not encoded_content:

        return None


    try:

        # GitHub normally includes newlines
        # in Base64 content.

        encoded_content = (
            encoded_content
            .replace("\n", "")
            .replace("\r", "")
        )


        decoded = base64.b64decode(
            encoded_content
        )


        # UTF-8 first.

        try:

            return decoded.decode(
                "utf-8"
            )

        except UnicodeDecodeError:

            # ------------------------------------------------
            # Fallback for source files using another encoding.
            # ------------------------------------------------

            return decoded.decode(
                "utf-8",
                errors="replace"
            )


    except Exception:

        return None


# ============================================================
# FILE CATEGORY DETECTION
# ============================================================

def categorize_file(
    file_path
):
    """
    Categorize repository files for Gitora's UI
    and AI context.
    """

    path = str(
        file_path or ""
    ).lower().strip()

    filename = (
        path.split("/")[-1]
        if path
        else ""
    )


    categories = []


    # ========================================================
    # ENTRY POINTS
    # ========================================================

    entry_points = {
        "app.py",
        "main.py",
        "server.py",
        "manage.py",
        "run.py",
        "index.js",
        "server.js",
        "main.js",
        "index.ts",
        "main.ts"
    }


    if filename in entry_points:

        categories.append(
            "entry-point"
        )


    # ========================================================
    # FLASK / DJANGO / BACKEND ROUTES
    # ========================================================

    route_keywords = [
        "route",
        "routes",
        "view",
        "views",
        "controller",
        "controllers",
        "endpoint",
        "api"
    ]


    if any(
        keyword in path
        for keyword in route_keywords
    ):

        categories.append(
            "routes"
        )


    # ========================================================
    # FRONTEND
    # ========================================================

    frontend_extensions = (
        ".html",
        ".htm",
        ".jsx",
        ".tsx",
        ".vue",
        ".svelte"
    )


    if path.endswith(
        frontend_extensions
    ):

        categories.append(
            "frontend"
        )


    # ========================================================
    # JAVASCRIPT / TYPESCRIPT
    # ========================================================

    if path.endswith(
        (
            ".js",
            ".jsx",
            ".ts",
            ".tsx"
        )
    ):

        categories.append(
            "javascript"
        )


    # ========================================================
    # PYTHON
    # ========================================================

    if path.endswith(
        ".py"
    ):

        categories.append(
            "python"
        )


    # ========================================================
    # DATABASE
    # ========================================================

    database_keywords = [
        "model",
        "models",
        "database",
        "db",
        "schema",
        "migration",
        "migrations"
    ]


    if any(
        keyword in path
        for keyword in database_keywords
    ):

        categories.append(
            "database"
        )


    database_extensions = (
        ".sql",
        ".sqlite",
        ".sqlite3",
        ".db"
    )


    if path.endswith(
        database_extensions
    ):

        categories.append(
            "database"
        )


    # ========================================================
    # AUTHENTICATION
    # ========================================================

    auth_keywords = [
        "auth",
        "authentication",
        "authorize",
        "authorization",
        "login",
        "logout",
        "signup",
        "register",
        "session",
        "jwt",
        "oauth",
        "permission"
    ]


    if any(
        keyword in path
        for keyword in auth_keywords
    ):

        categories.append(
            "authentication"
        )


    # ========================================================
    # SERVICES
    # ========================================================

    service_keywords = [
        "service",
        "services",
        "utils",
        "utility",
        "utilities",
        "helper",
        "helpers"
    ]


    if any(
        keyword in path
        for keyword in service_keywords
    ):

        categories.append(
            "services"
        )


    # ========================================================
    # CONFIGURATION
    # ========================================================

    config_files = {
        ".env",
        ".env.example",
        ".env.sample",
        "config.py",
        "settings.py",
        "config.js",
        "settings.js",
        "dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
        "render.yaml",
        "vercel.json",
        "netlify.toml"
    }


    if filename in config_files:

        categories.append(
            "configuration"
        )


    # ========================================================
    # DEPENDENCIES
    # ========================================================

    dependency_files = {
        "requirements.txt",
        "pyproject.toml",
        "pipfile",
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "poetry.lock"
    }


    if filename in dependency_files:

        categories.append(
            "dependencies"
        )


    # ========================================================
    # DOCUMENTATION
    # ========================================================

    documentation_files = {
        "readme",
        "readme.md",
        "readme.txt",
        "contributing.md",
        "changelog.md",
        "license",
        "license.md"
    }


    if (
        filename in documentation_files
        or path.startswith("docs/")
    ):

        categories.append(
            "documentation"
        )


    # ========================================================
    # CSS
    # ========================================================

    if path.endswith(
        (
            ".css",
            ".scss",
            ".sass",
            ".less"
        )
    ):

        categories.append(
            "styling"
        )


    # ========================================================
    # TESTING
    # ========================================================

    if (
        "test" in filename
        or "tests/" in path
        or "testing/" in path
    ):

        categories.append(
            "testing"
        )


    # ========================================================
    # OTHER
    # ========================================================

    if not categories:

        categories.append(
            "other"
        )


    # Remove duplicates while preserving order.

    return list(
        dict.fromkeys(
            categories
        )
    )


# ============================================================
# CHECK GITHUB CONNECTION
# ============================================================

def test_github_connection():
    """
    Small GitHub API health check.
    """

    try:

        api_url = (
            f"{GITHUB_API}/rate_limit"
        )

        _, data = github_get(
            api_url,
            timeout=10
        )

        rate = data.get(
            "rate",
            {}
        )

        return {
            "ok": True,

            "authenticated":
                bool(GITHUB_TOKEN),

            "remaining":
                rate.get(
                    "remaining"
                ),

            "limit":
                rate.get(
                    "limit"
                )
        }

    except Exception as error:

        return {
            "ok": False,
            "authenticated":
                bool(GITHUB_TOKEN),
            "message":
                str(error)
        }