import os
import base64
import requests

from dotenv import load_dotenv


# =====================================================
# LOAD ENVIRONMENT VARIABLES
# =====================================================

load_dotenv()


# =====================================================
# GITHUB CONFIGURATION
# =====================================================

GITHUB_API = "https://api.github.com"

GITHUB_TOKEN = os.getenv(
    "GITHUB_TOKEN"
)


# GitHub recommends these headers for REST API requests.
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


# Add authentication only when a token exists.
if GITHUB_TOKEN:

    HEADERS["Authorization"] = (
        f"Bearer {GITHUB_TOKEN}"
    )


# =====================================================
# INTERNAL REQUEST HELPER
# =====================================================

def github_get(
    api_url,
    timeout=30
):
    """
    Make an authenticated GET request to GitHub.

    Centralizing requests here ensures that every
    GitHub API call uses the same headers and error
    handling.
    """

    try:

        response = requests.get(
            api_url,
            headers=HEADERS,
            timeout=timeout
        )

    except requests.RequestException as error:

        print(
            "GITHUB CONNECTION ERROR:",
            error
        )

        raise ValueError(
            "Unable to connect to GitHub. "
            "Please check your internet connection."
        )

    print(
        "GITHUB STATUS:",
        response.status_code,
        api_url
    )

    # -------------------------------------------------
    # SUCCESS
    # -------------------------------------------------

    if response.status_code == 200:

        return response

    # -------------------------------------------------
    # RATE LIMIT / FORBIDDEN
    # -------------------------------------------------

    if response.status_code == 403:

        remaining = response.headers.get(
            "X-RateLimit-Remaining"
        )

        reset = response.headers.get(
            "X-RateLimit-Reset"
        )

        message = ""

        try:

            error_data = response.json()

            message = error_data.get(
                "message",
                ""
            )

        except ValueError:

            pass

        print(
            "GITHUB 403:",
            message
        )

        print(
            "RATE LIMIT REMAINING:",
            remaining
        )

        print(
            "RATE LIMIT RESET:",
            reset
        )

        if remaining == "0":

            raise ValueError(
                "GitHub API rate limit exceeded. "
                "Please wait and try again."
            )

        if GITHUB_TOKEN:

            raise ValueError(
                "GitHub rejected the API request "
                "with 403 Forbidden. Your GitHub "
                "token may be invalid, expired, or "
                "does not have access to this repository."
            )

        raise ValueError(
            "GitHub returned 403 Forbidden. "
            "Configure GITHUB_TOKEN in your .env "
            "file and try again."
        )

    # -------------------------------------------------
    # NOT FOUND
    # -------------------------------------------------

    if response.status_code == 404:

        raise ValueError(
            "GitHub repository or resource was not found. "
            "Check the repository URL and permissions."
        )

    # -------------------------------------------------
    # UNAUTHORIZED
    # -------------------------------------------------

    if response.status_code == 401:

        raise ValueError(
            "GitHub authentication failed. "
            "Your GITHUB_TOKEN may be invalid or expired."
        )

    # -------------------------------------------------
    # OTHER ERROR
    # -------------------------------------------------

    try:

        error_data = response.json()

        message = error_data.get(
            "message",
            "Unknown GitHub error."
        )

    except ValueError:

        message = (
            "Unknown GitHub API error."
        )

    raise ValueError(
        f"GitHub returned status "
        f"{response.status_code}: {message}"
    )


# =====================================================
# GET REPOSITORY INFORMATION
# =====================================================

def get_repository_info(repo_url):

    repo_url = (
        repo_url
        .strip()
        .rstrip("/")
    )

    if repo_url.endswith(".git"):

        repo_url = repo_url[:-4]

    parts = repo_url.split("/")

    if (
        len(parts) < 5
        or parts[2].lower() != "github.com"
    ):

        raise ValueError(
            "Please enter a valid GitHub repository URL."
        )

    owner = parts[3]
    repo = parts[4]

    api_url = (
        f"{GITHUB_API}/repos/"
        f"{owner}/{repo}"
    )

    response = github_get(
        api_url,
        timeout=20
    )

    try:

        data = response.json()

    except ValueError:

        raise ValueError(
            "GitHub returned invalid repository data."
        )

    return {

        "name":
            data.get("name"),

        "full_name":
            data.get("full_name"),

        "description":
            data.get("description"),

        "language":
            data.get("language"),

        "stars":
            data.get("stargazers_count"),

        "forks":
            data.get("forks_count"),

        "open_issues":
            data.get("open_issues_count"),

        "default_branch":
            data.get("default_branch"),

        "owner":
            owner,

        "repo":
            repo,

        "url":
            data.get("html_url")

    }


# =====================================================
# GET ALL REPOSITORY FILES
# =====================================================

def get_repository_files(
    owner,
    repo,
    branch
):

    api_url = (
        f"{GITHUB_API}/repos/"
        f"{owner}/{repo}/git/trees/"
        f"{branch}?recursive=1"
    )

    response = github_get(
        api_url,
        timeout=30
    )

    try:

        data = response.json()

    except ValueError:

        raise ValueError(
            "GitHub returned invalid repository tree data."
        )

    # GitHub can indicate that a recursive tree is
    # truncated. We warn rather than silently pretending
    # we received every file.
    if data.get("truncated"):

        print(
            "WARNING: GitHub repository tree "
            "is truncated."
        )

    files = []

    for item in data.get(
        "tree",
        []
    ):

        if item.get("type") != "blob":

            continue

        path = item.get(
            "path"
        )

        if not path:

            continue

        files.append({

            "path": path,

            "type": "file"

        })

    return files


# =====================================================
# GET INDIVIDUAL FILE CONTENT
# =====================================================

def get_file_content(
    owner,
    repo,
    file_path,
    branch
):

    api_url = (
        f"{GITHUB_API}/repos/"
        f"{owner}/{repo}/contents/"
        f"{file_path}?ref={branch}"
    )

    try:

        response = github_get(
            api_url,
            timeout=30
        )

    except ValueError as error:

        print(
            "GITHUB FILE ERROR:",
            file_path,
            error
        )

        # Preserve your existing behaviour:
        # callers can skip an individual file.
        return None

    try:

        data = response.json()

    except ValueError:

        print(
            "GITHUB FILE JSON ERROR:",
            file_path
        )

        return None

    if data.get("type") != "file":

        print(
            "GITHUB RESOURCE IS NOT A FILE:",
            file_path
        )

        return None

    encoded_content = data.get(
        "content",
        ""
    )

    if not encoded_content:

        print(
            "GITHUB FILE HAS NO CONTENT:",
            file_path
        )

        return None

    try:

        # GitHub normally returns Base64 content with
        # newline characters. Removing whitespace makes
        # decoding more robust.
        encoded_content = (
            encoded_content
            .replace("\n", "")
            .replace("\r", "")
        )

        content = base64.b64decode(
            encoded_content
        ).decode(
            "utf-8",
            errors="ignore"
        )

        print(
            "GITHUB FILE LOADED:",
            file_path
        )

        return content

    except Exception as error:

        print(
            "FILE DECODE ERROR:",
            file_path,
            error
        )

        return None


# =====================================================
# CATEGORIZE FILE
# =====================================================

def categorize_file(file_path):

    path = file_path.lower()

    categories = []

    # -------------------------------------------------
    # ENTRY POINTS
    # -------------------------------------------------

    if any(
        name in path
        for name in [
            "app.py",
            "main.py",
            "server.py",
            "run.py",
            "index.js",
            "main.js",
            "server.js"
        ]
    ):

        categories.append(
            "Entry Point"
        )

    # -------------------------------------------------
    # ROUTES / API
    # -------------------------------------------------

    if any(
        name in path
        for name in [
            "route",
            "routes",
            "api",
            "controller",
            "views"
        ]
    ):

        categories.append(
            "Routes / API"
        )

    # -------------------------------------------------
    # DATABASE
    # -------------------------------------------------

    if any(
        name in path
        for name in [
            "model",
            "models",
            "database",
            "db",
            "schema"
        ]
    ):

        categories.append(
            "Database"
        )

    # -------------------------------------------------
    # AUTHENTICATION
    # -------------------------------------------------

    if any(
        name in path
        for name in [
            "auth",
            "login",
            "register",
            "signup",
            "user"
        ]
    ):

        categories.append(
            "Authentication"
        )

    # -------------------------------------------------
    # CONFIGURATION
    # -------------------------------------------------

    if any(
        name in path
        for name in [
            "config",
            ".env",
            "settings"
        ]
    ):

        categories.append(
            "Configuration"
        )

    # -------------------------------------------------
    # DEPENDENCIES
    # -------------------------------------------------

    if any(
        name in path
        for name in [
            "requirements.txt",
            "package.json",
            "pyproject.toml",
            "pom.xml",
            "build.gradle"
        ]
    ):

        categories.append(
            "Dependencies"
        )

    # -------------------------------------------------
    # DOCUMENTATION
    # -------------------------------------------------

    if any(
        name in path
        for name in [
            "readme",
            "documentation",
            "docs/"
        ]
    ):

        categories.append(
            "Documentation"
        )

    # -------------------------------------------------
    # FRONTEND
    # -------------------------------------------------

    if any(
        path.endswith(ext)
        for ext in [
            ".html",
            ".css",
            ".scss",
            ".jsx",
            ".tsx"
        ]
    ):

        categories.append(
            "Frontend"
        )

    # -------------------------------------------------
    # JAVASCRIPT
    # -------------------------------------------------

    if path.endswith(".js"):

        categories.append(
            "JavaScript"
        )

    # -------------------------------------------------
    # PYTHON
    # -------------------------------------------------

    if path.endswith(".py"):

        categories.append(
            "Python"
        )

    # -------------------------------------------------
    # OTHER
    # -------------------------------------------------

    if not categories:

        categories.append(
            "Other"
        )

    return categories