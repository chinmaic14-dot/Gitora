# ============================================================
# GITORA ROUTES
# Gemini removed
# Remote AI compatible
# ============================================================

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    send_file
)

from urllib.parse import urlparse

from app import db

from app.models import SavedFileSelection

from app.services.github_service import (
    get_repository_info,
    get_repository_files,
    get_file_content,
    categorize_file
)

from app.services.ai_service import (
    analyze_repository,
    analyze_single_file,
    answer_repository_question,
    generate_rebuild_strategies,
    test_ai_connection
)

from app.services.pdf_service import (
    generate_repository_pdf
)


# ============================================================
# BLUEPRINT
# ============================================================

main = Blueprint(
    "main",
    __name__
)


# ============================================================
# AI CACHE
# ============================================================

AI_ANALYSIS_CACHE = {}


# ============================================================
# REQUEST DATA HELPER
# ============================================================

def get_request_data():

    data = request.get_json(
        silent=True
    )

    if isinstance(data, dict):
        return data

    data = {}

    for key in request.form:

        values = request.form.getlist(key)

        if len(values) > 1:
            data[key] = values
        else:
            data[key] = request.form.get(key)

    return data


# ============================================================
# REPOSITORY HELPERS
# ============================================================

def get_repository_identifier(repository):

    if isinstance(repository, dict):

        return (
            repository.get("full_name")
            or repository.get("name")
            or ""
        )

    return str(repository or "").strip()


def parse_repository_input(repository_value):

    repository_value = (
        str(repository_value or "")
        .strip()
        .rstrip("/")
    )

    if repository_value.endswith(".git"):
        repository_value = repository_value[:-4]

    if (
        repository_value.startswith(
            "http://"
        )
        or repository_value.startswith(
            "https://"
        )
    ):

        parsed = urlparse(
            repository_value
        )

        if parsed.netloc.lower() != "github.com":
            raise ValueError(
                "Please enter a valid GitHub repository URL."
            )

        parts = [
            item
            for item in parsed.path.split("/")
            if item
        ]

    else:

        parts = [
            item
            for item in repository_value.split("/")
            if item
        ]

    if len(parts) < 2:

        raise ValueError(
            "Repository must be in owner/repository format."
        )

    owner = parts[0]
    repo = parts[1]

    return owner, repo


def load_repository(repository_value):

    owner, repo = parse_repository_input(
        repository_value
    )

    repository_url = (
        f"https://github.com/"
        f"{owner}/{repo}"
    )

    repository = get_repository_info(
        repository_url
    )

    return repository


def get_owner(repository):

    if isinstance(repository, dict):
        return repository.get("owner", "")

    return ""


def get_repo_name(repository):

    if isinstance(repository, dict):
        return repository.get("repo", "")

    return ""


def get_branch(repository):

    if isinstance(repository, dict):

        return (
            repository.get("default_branch")
            or "main"
        )

    return "main"


# ============================================================
# SAVED FILES
# ============================================================

def get_saved_file_paths(
    repository_name
):

    if not repository_name:
        return []

    rows = (
        SavedFileSelection.query
        .filter_by(
            repository=repository_name
        )
        .all()
    )

    return [
        row.file_path
        for row in rows
    ]


def save_selected_file_paths(
    repository_name,
    file_paths
):

    SavedFileSelection.query.filter_by(
        repository=repository_name
    ).delete()

    for path in file_paths:

        path = str(path).strip()

        if not path:
            continue

        db.session.add(
            SavedFileSelection(
                repository=repository_name,
                file_path=path
            )
        )

    db.session.commit()


# ============================================================
# LOAD SOURCE FILES
# ============================================================

def load_source_files(
    repository,
    file_paths
):

    owner = get_owner(
        repository
    )

    repo = get_repo_name(
        repository
    )

    branch = get_branch(
        repository
    )

    source_files = []

    for path in file_paths:

        content = get_file_content(
            owner,
            repo,
            path,
            branch
        )

        if content is None:
            continue

        source_files.append({
            "path": path,
            "content": content,
            "categories":
                categorize_file(path)
        })

    return source_files


# ============================================================
# VALIDATE AI ANALYSIS
# ============================================================

def is_valid_ai_analysis(
    analysis
):

    if not isinstance(
        analysis,
        dict
    ):
        return False

    return any(
        analysis.get(key)
        for key in [
            "project_summary",
            "technology_stack",
            "file_analysis",
            "architecture"
        ]
    )


# ============================================================
# HOME
# ============================================================

@main.route("/")
def index():

    return render_template(
        "index.html"
    )


# ============================================================
# ANALYZE PAGE
# ============================================================

@main.route(
    "/analyze",
    methods=["GET", "POST"]
)
def analyze():

    repository_value = (
        request.values.get(
            "repository"
        )
        or request.values.get(
            "repo"
        )
        or ""
    )

    if not repository_value:

        return render_template(
            "index.html",
            error="Please enter a GitHub repository URL."
        )

    try:

        repository = load_repository(
            repository_value
        )

        owner = repository["owner"]
        repo = repository["repo"]

        branch = repository.get(
            "default_branch"
        ) or "main"

        files = get_repository_files(
            owner,
            repo,
            branch
        )

        saved_paths = (
            get_saved_file_paths(
                repository["full_name"]
            )
        )

        source_files = load_source_files(
            repository,
            saved_paths
        )

        return render_template(
            "analysis.html",
            repository=repository,
            files=files,
            saved_files=saved_paths,
            source_files=source_files
        )

    except Exception as error:

        return render_template(
            "index.html",
            error=str(error)
        )


# ============================================================
# SAVE FILES
# ============================================================

@main.route(
    "/save-files",
    methods=["POST"]
)
def save_files():

    data = get_request_data()

    repository_value = (
        data.get("repository")
        or data.get("repo")
    )

    file_paths = (
        data.get("selected_files")
        or data.get("files")
        or []
    )

    if isinstance(
        file_paths,
        str
    ):
        file_paths = [
            file_paths
        ]

    if not repository_value:

        if request.is_json:

            return jsonify({
                "success": False,
                "error":
                    "Repository information is missing."
            }), 400

        return redirect(
            url_for("main.index")
        )

    try:

        repository = load_repository(
            repository_value
        )

        repository_name = (
            repository["full_name"]
        )

        save_selected_file_paths(
            repository_name,
            file_paths
        )

        AI_ANALYSIS_CACHE.pop(
            repository_name,
            None
        )

        if request.is_json:

            return jsonify({
                "success": True,
                "message":
                    "Selected files saved successfully.",
                "count": len(file_paths)
            })

        return redirect(
            url_for(
                "main.analyze",
                repository=repository_name
            )
        )

    except Exception as error:

        if request.is_json:

            return jsonify({
                "success": False,
                "error": str(error)
            }), 500

        return redirect(
            url_for(
                "main.index"
            )
        )


# ============================================================
# OVERALL AI ANALYSIS
# ============================================================

@main.route(
    "/ai-analyze",
    methods=["POST"]
)
def ai_analyze():

    data = get_request_data()

    repository_value = (
        data.get("repository")
        or data.get("repo")
    )

    if not repository_value:

        return jsonify({
            "success": False,
            "error":
                "Repository information is missing."
        }), 400

    try:

        repository = load_repository(
            repository_value
        )

        repository_name = (
            repository["full_name"]
        )

        file_paths = (
            data.get("selected_files")
            or data.get("files")
            or data.get("source_files")
        )

        if isinstance(
            file_paths,
            str
        ):
            file_paths = [
                file_paths
            ]

        if not file_paths:

            file_paths = (
                get_saved_file_paths(
                    repository_name
                )
            )

        if not file_paths:

            return jsonify({
                "success": False,
                "error":
                    "No files selected. "
                    "Please select and save files first."
            }), 400

        source_files = load_source_files(
            repository,
            file_paths
        )

        if not source_files:

            return jsonify({
                "success": False,
                "error":
                    "Unable to read the selected files from GitHub."
            }), 400

        cache_key = (
            repository_name
            + "|"
            + "|".join(
                sorted(file_paths)
            )
        )

        if cache_key in AI_ANALYSIS_CACHE:

            return jsonify({
                "success": True,
                "analysis":
                    AI_ANALYSIS_CACHE[
                        cache_key
                    ],
                "cached": True
            })

        analysis = analyze_repository(
            repository,
            source_files
        )

        AI_ANALYSIS_CACHE[
            cache_key
        ] = analysis

        return jsonify({
            "success": True,
            "analysis": analysis,
            "cached": False
        })

    except Exception as error:

        print(
            "OVERALL AI ERROR:",
            error
        )

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ============================================================
# REBUILD OPTIONS
# ============================================================

@main.route(
    "/rebuild-options",
    methods=["POST"]
)
def rebuild_options():

    data = get_request_data()

    repository_value = (
        data.get("repository")
        or data.get("repo")
    )

    if not repository_value:

        return jsonify({
            "success": False,
            "error":
                "Repository information is missing."
        }), 400

    try:

        repository = load_repository(
            repository_value
        )

        repository_name = (
            repository["full_name"]
        )

        file_paths = (
            data.get("selected_files")
            or data.get("files")
            or []
        )

        if isinstance(
            file_paths,
            str
        ):
            file_paths = [
                file_paths
            ]

        if not file_paths:

            file_paths = (
                get_saved_file_paths(
                    repository_name
                )
            )

        source_files = load_source_files(
            repository,
            file_paths
        )

        result = (
            generate_rebuild_strategies(
                repository,
                source_files
            )
        )

        return jsonify({
            "success": True,
            **result
        })

    except Exception as error:

        print(
            "REBUILD AI ERROR:",
            error
        )

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ============================================================
# SINGLE FILE AI ANALYSIS
# ============================================================

@main.route(
    "/analyze-file",
    methods=["POST"]
)
def analyze_file():

    data = get_request_data()

    repository_value = (
        data.get("repository")
        or data.get("repo")
    )

    file_path = (
        data.get("file_path")
        or data.get("file")
    )

    if not repository_value:

        return jsonify({
            "success": False,
            "error":
                "Repository information is missing."
        }), 400

    if not file_path:

        return jsonify({
            "success": False,
            "error":
                "File path is missing."
        }), 400

    try:

        repository = load_repository(
            repository_value
        )

        content = get_file_content(
            repository["owner"],
            repository["repo"],
            file_path,
            repository.get(
                "default_branch"
            ) or "main"
        )

        if content is None:

            return jsonify({
                "success": False,
                "error":
                    "Unable to load this file from GitHub."
            }), 404

        analysis = analyze_single_file(
            repository,
            file_path,
            content
        )

        return jsonify({
            "success": True,
            "analysis": analysis
        })

    except Exception as error:

        print(
            "FILE AI ERROR:",
            error
        )

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ============================================================
# ASK AI
# ============================================================

@main.route(
    "/ask-ai",
    methods=["POST"]
)
def ask_ai():

    data = get_request_data()

    repository_value = (
        data.get("repository")
        or data.get("repo")
    )

    question = str(
        data.get("question")
        or ""
    ).strip()

    if not repository_value:

        return jsonify({
            "success": False,
            "error":
                "Repository information is missing."
        }), 400

    if not question:

        return jsonify({
            "success": False,
            "error":
                "Please enter a question."
        }), 400

    try:

        repository = load_repository(
            repository_value
        )

        repository_name = (
            repository["full_name"]
        )

        file_paths = (
            get_saved_file_paths(
                repository_name
            )
        )

        if not file_paths:

            return jsonify({
                "success": False,
                "error":
                    "No saved files available for AI."
            }), 400

        source_files = load_source_files(
            repository,
            file_paths
        )

        answer = answer_repository_question(
            repository,
            source_files,
            question
        )

        return jsonify({
            "success": True,
            "answer": answer
        })

    except Exception as error:

        print(
            "ASK AI ERROR:",
            error
        )

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ============================================================
# DOWNLOAD PDF REPORT
# ============================================================

@main.route(
    "/download-report",
    methods=["POST"]
)
def download_report():

    data = get_request_data()

    repository_value = (
        data.get("repository")
        or data.get("repo")
    )

    if not repository_value:

        return jsonify({
            "success": False,
            "error":
                "Repository information is missing."
        }), 400

    try:

        repository = load_repository(
            repository_value
        )

        repository_name = (
            repository["full_name"]
        )

        file_paths = (
            data.get("selected_files")
            or data.get("files")
            or []
        )

        if isinstance(
            file_paths,
            str
        ):
            file_paths = [
                file_paths
            ]

        if not file_paths:

            file_paths = (
                get_saved_file_paths(
                    repository_name
                )
            )

        source_files = load_source_files(
            repository,
            file_paths
        )

        analysis = (
            data.get("ai_analysis")
            or data.get("analysis")
        )

        # HTML form values arrive as strings.
        if isinstance(
            analysis,
            str
        ):
            try:
                import json
                analysis = json.loads(
                    analysis
                )
            except Exception:
                analysis = None

        cache_key = (
            repository_name
            + "|"
            + "|".join(
                sorted(file_paths)
            )
        )

        if not is_valid_ai_analysis(
            analysis
        ):

            analysis = (
                AI_ANALYSIS_CACHE.get(
                    cache_key
                )
            )

        if not is_valid_ai_analysis(
            analysis
        ):

            analysis = analyze_repository(
                repository,
                source_files
            )

            AI_ANALYSIS_CACHE[
                cache_key
            ] = analysis

        pdf = generate_repository_pdf(
            repository,
            source_files,
            analysis
        )

        return send_file(
            pdf,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=(
                f"Gitora_{repository_name.replace('/', '_')}.pdf"
            )
        )

    except Exception as error:

        print(
            "PDF ERROR:",
            error
        )

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500


# ============================================================
# AI HEALTH
# ============================================================

@main.route(
    "/ai-health",
    methods=["GET"]
)
def ai_health():

    result = test_ai_connection()

    status_code = (
        200
        if result.get("ok")
        else 503
    )

    return jsonify({
        "success": result.get("ok"),
        "ai_configured":
            bool(result.get("model")),
        "model":
            result.get("model", ""),
        "message":
            result.get("message", "")
    }), status_code