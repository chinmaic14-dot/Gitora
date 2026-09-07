# ============================================================
# GITORA - MAIN ROUTES
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
    get_repository,
    get_repository_files,
    get_file_content
)

from app.services.ai_service import (
    analyze_repository,
    analyze_single_file,
    answer_repository_question,
    generate_rebuild_strategies,
    get_gemini_client,
    GEMINI_API_KEY,
    MODEL
)

from app.services.pdf_service import generate_repository_pdf


# ============================================================
# BLUEPRINT
# ============================================================

main = Blueprint("main", __name__)


# ============================================================
# AI CACHE
# ============================================================

AI_ANALYSIS_CACHE = {}


# ============================================================
# HELPER - NORMALIZE REPOSITORY
# ============================================================

def normalize_repository(repository):
    """
    Convert repository information into the format expected
    by the Gitora application.
    """

    if not repository:
        return {}

    if isinstance(repository, dict):
        return repository

    return {}


# ============================================================
# HELPER - REPOSITORY IDENTIFICATION
# ============================================================

def get_repository_identifier(repository):
    """
    Return a stable identifier for the repository.
    """

    if not repository:
        return ""

    return (
        repository.get("full_name")
        or repository.get("html_url")
        or repository.get("name")
        or ""
    )


# ============================================================
# HELPER - VALIDATE AI ANALYSIS
# ============================================================

def is_valid_ai_analysis(analysis):

    if not isinstance(analysis, dict):
        return False

    failure_values = [
        "unable to connect ai service",
        "unable to connect to ai service",
        "gemini could not analyze the repository",
        "gemini ai request failed",
        "ai service unavailable",
        "ai analysis failed"
    ]

    for value in analysis.values():

        if isinstance(value, str):

            lower_value = value.lower()

            for failure in failure_values:

                if failure in lower_value:
                    return False

    # At least one meaningful field should exist.
    return bool(
        analysis.get("project_summary")
        or analysis.get("technology_stack")
        or analysis.get("file_analysis")
        or analysis.get("architecture")
    )


# ============================================================
# HELPER - SAVED FILE PATHS
# ============================================================

def get_saved_file_paths(repository_name):

    if not repository_name:
        return []

    try:

        saved = (
            SavedFileSelection.query
            .filter_by(repository=repository_name)
            .all()
        )

        paths = []

        for item in saved:

            path = getattr(item, "file_path", None)

            if not path:
                path = getattr(item, "path", None)

            if path:
                paths.append(path)

        return paths

    except Exception:

        return []


# ============================================================
# HELPER - LOAD SOURCE FILES
# ============================================================

def load_source_files(repository, file_paths):

    source_files = []

    if not repository:
        return source_files

    owner = repository.get("owner", {})

    if isinstance(owner, dict):
        owner = owner.get("login", "")

    repo_name = (
        repository.get("name")
        or ""
    )

    branch = (
        repository.get("default_branch")
        or "main"
    )

    for path in file_paths or []:

        try:

            content = get_file_content(
                owner,
                repo_name,
                path,
                branch
            )

            if content is None:
                continue

            source_files.append({
                "path": path,
                "content": content
            })

            print(
                f"GITHUB FILE LOADED: {path}",
                flush=True
            )

        except Exception as exc:

            print(
                f"⚠️ Failed loading file {path}: {exc}",
                flush=True
            )

    return source_files


# ============================================================
# HELPER - GET REPOSITORY FROM URL
# ============================================================

def parse_github_url(repository_url):

    repository_url = (
        repository_url or ""
    ).strip()

    if not repository_url:
        return None, None

    parsed = urlparse(repository_url)

    path_parts = [
        part
        for part in parsed.path.split("/")
        if part
    ]

    if len(path_parts) < 2:
        return None, None

    owner = path_parts[0]
    repo = path_parts[1]

    if repo.endswith(".git"):
        repo = repo[:-4]

    return owner, repo


# ============================================================
# HOME
# ============================================================

@main.route("/")
def index():

    return render_template(
        "index.html"
    )


# ============================================================
# ANALYZE REPOSITORY PAGE
# ============================================================

@main.route("/analyze", methods=["GET", "POST"])
def analyze():

    print(
        "🔥 GITORA /analyze ROUTE REACHED",
        flush=True
    )

    repository_url = (
        request.form.get("repository_url")
        or request.args.get("repository_url")
        or request.form.get("repo_url")
        or request.args.get("repo_url")
        or ""
    ).strip()

    if not repository_url:

        return redirect(
            url_for("main.index")
        )

    try:

        # ----------------------------------------------------
        # LOAD REPOSITORY
        # ----------------------------------------------------

        repository = get_repository(
            repository_url
        )

        if not repository:

            return render_template(
                "index.html",
                error="Unable to load GitHub repository."
            )

        repository = normalize_repository(
            repository
        )

        print(
            f"Repository loaded: {repository}",
            flush=True
        )

        repository_name = get_repository_identifier(
            repository
        )

        # ----------------------------------------------------
        # LOAD FILE TREE
        # ----------------------------------------------------

        print(
            "Loading repository files...",
            flush=True
        )

        files = get_repository_files(
            repository
        )

        if files is None:
            files = []

        print(
            f"Repository files: {len(files)}",
            flush=True
        )

        # ----------------------------------------------------
        # SAVED FILES
        # ----------------------------------------------------

        saved_file_paths = get_saved_file_paths(
            repository_name
        )

        print(
            f"Saved files: {saved_file_paths}",
            flush=True
        )

        # ----------------------------------------------------
        # LOAD SOURCE FILES
        # ----------------------------------------------------

        source_files = load_source_files(
            repository,
            saved_file_paths
        )

        print(
            f"Source files loaded: {len(source_files)}",
            flush=True
        )

        return render_template(
            "analysis.html",
            repository=repository,
            files=files,
            saved_files=saved_file_paths,
            source_files=source_files,
            ai_analysis=None
        )

    except Exception as exc:

        import traceback

        traceback.print_exc()

        return render_template(
            "index.html",
            error=f"Unable to analyze repository: {exc}"
        )


# ============================================================
# SAVE SELECTED FILES
# ============================================================

@main.route("/save-files", methods=["POST"])
def save_files():

    print(
        "🔥 GITORA /save-files ROUTE REACHED",
        flush=True
    )

    try:

        repository_name = (
            request.form.get("repository")
            or request.form.get("repository_name")
            or request.form.get("repo")
            or ""
        ).strip()

        repository_url = (
            request.form.get("repository_url")
            or ""
        ).strip()

        # ----------------------------------------------------
        # JSON REQUEST SUPPORT
        # ----------------------------------------------------

        if request.is_json:

            data = request.get_json(
                silent=True
            ) or {}

            repository_name = (
                data.get("repository")
                or data.get("repository_name")
                or repository_name
            )

            repository_url = (
                data.get("repository_url")
                or repository_url
            )

            selected_files = (
                data.get("files")
                or data.get("selected_files")
                or []
            )

        else:

            selected_files = (
                request.form.getlist("files")
                or request.form.getlist("selected_files")
            )

        print(
            f"Repository: {repository_name}",
            flush=True
        )

        print(
            f"Selected files: {selected_files}",
            flush=True
        )

        # ----------------------------------------------------
        # DELETE OLD SELECTIONS
        # ----------------------------------------------------

        SavedFileSelection.query.filter_by(
            repository=repository_name
        ).delete()

        # ----------------------------------------------------
        # SAVE NEW SELECTIONS
        # ----------------------------------------------------

        for path in selected_files:

            path = str(path).strip()

            if not path:
                continue

            item = SavedFileSelection(
                repository=repository_name,
                file_path=path
            )

            db.session.add(item)

        db.session.commit()

        # ----------------------------------------------------
        # CLEAR AI CACHE
        # ----------------------------------------------------

        AI_ANALYSIS_CACHE.pop(
            repository_name,
            None
        )

        print(
            "Saved successfully.",
            flush=True
        )

        # ----------------------------------------------------
        # JSON RESPONSE
        # ----------------------------------------------------

        if request.is_json:

            return jsonify({
                "success": True,
                "files": selected_files
            })

        # ----------------------------------------------------
        # RELOAD ANALYSIS PAGE
        # ----------------------------------------------------

        if not repository_url:

            repository_url = (
                request.form.get("url")
                or request.form.get("repo_url")
                or ""
            ).strip()

        if repository_url:

            return redirect(
                url_for(
                    "main.analyze",
                    repository_url=repository_url
                )
            )

        # If URL is unavailable, render through repository name
        # where possible.

        repository = {
            "full_name": repository_name,
            "name": repository_name.split("/")[-1]
            if "/" in repository_name
            else repository_name,
            "owner": {
                "login": repository_name.split("/")[0]
                if "/" in repository_name
                else ""
            },
            "default_branch": "main"
        }

        files = get_repository_files(
            repository
        ) or []

        saved_paths = get_saved_file_paths(
            repository_name
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
            source_files=source_files,
            ai_analysis=None
        )

    except Exception as exc:

        db.session.rollback()

        import traceback

        traceback.print_exc()

        if request.is_json:

            return jsonify({
                "success": False,
                "error": str(exc)
            }), 500

        return redirect(
            url_for("main.index")
        )


# ============================================================
# AI FULL REPOSITORY ANALYSIS
# ============================================================

@main.route("/ai-analyze", methods=["POST"])
def ai_analyze():

    print(
        "🔥 GITORA /ai-analyze ROUTE REACHED",
        flush=True
    )

    try:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        # ----------------------------------------------------
        # REPOSITORY
        # ----------------------------------------------------

        repository = data.get(
            "repository"
        )

        repository_url = (
            data.get("repository_url")
            or data.get("repo_url")
            or ""
        ).strip()

        # ----------------------------------------------------
        # DIRECT FILES FROM BROWSER
        # ----------------------------------------------------

        browser_files = (
            data.get("files")
            or data.get("source_files")
            or []
        )

        print(
            f"Repository: {repository}",
            flush=True
        )

        print(
            f"Files received directly from browser: "
            f"{len(browser_files)}",
            flush=True
        )

        # ----------------------------------------------------
        # LOAD REPOSITORY IF ONLY URL WAS SENT
        # ----------------------------------------------------

        if isinstance(repository, str):

            repository_name = repository

            if repository_url:

                repository = get_repository(
                    repository_url
                )

            else:

                owner, repo_name = parse_github_url(
                    repository
                )

                if owner and repo_name:

                    repository = get_repository(
                        f"https://github.com/{owner}/{repo_name}"
                    )

        if not isinstance(repository, dict):

            if repository_url:

                repository = get_repository(
                    repository_url
                )

        if not repository:

            return jsonify({
                "success": False,
                "error": "Repository information is missing."
            }), 400

        repository = normalize_repository(
            repository
        )

        repository_name = get_repository_identifier(
            repository
        )

        if not repository_name:

            return jsonify({
                "success": False,
                "error": "Unable to identify repository."
            }), 400

        # ----------------------------------------------------
        # DETERMINE FILES
        # ----------------------------------------------------

        source_files = []

        if browser_files:

            for file in browser_files:

                if not isinstance(file, dict):
                    continue

                path = (
                    file.get("path")
                    or file.get("file")
                    or file.get("filename")
                )

                content = file.get(
                    "content",
                    ""
                )

                if path:

                    source_files.append({
                        "path": path,
                        "content": content or ""
                    })

        else:

            print(
                "⚠️ No files received from browser.",
                flush=True
            )

            saved_file_paths = get_saved_file_paths(
                repository_name
            )

            print(
                f"Files loaded from database: "
                f"{saved_file_paths}",
                flush=True
            )

            source_files = load_source_files(
                repository,
                saved_file_paths
            )

        if not source_files:

            return jsonify({
                "success": False,
                "error": (
                    "No saved files were found. "
                    "Please select and save at least one file."
                )
            }), 400

        print(
            f"Source files loaded: {len(source_files)}",
            flush=True
        )

        # ----------------------------------------------------
        # CACHE
        # ----------------------------------------------------

        cached_analysis = AI_ANALYSIS_CACHE.get(
            repository_name
        )

        if is_valid_ai_analysis(
            cached_analysis
        ):

            print(
                "✅ Returning cached AI analysis.",
                flush=True
            )

            return jsonify({
                "success": True,
                "analysis": cached_analysis
            })

        # ----------------------------------------------------
        # GEMINI
        # ----------------------------------------------------

        print(
            "🔥 SENDING REQUEST TO GEMINI",
            flush=True
        )

        print(
            f"Repository: {repository_name}",
            flush=True
        )

        print(
            f"Files sent to Gemini: {len(source_files)}",
            flush=True
        )

        result = analyze_repository(
            repository=repository,
            files=source_files
        )

        if not is_valid_ai_analysis(
            result
        ):

            return jsonify({
                "success": False,
                "error": (
                    "Gemini returned an incomplete "
                    "repository analysis."
                )
            }), 503

        # ----------------------------------------------------
        # CACHE RESULT
        # ----------------------------------------------------

        AI_ANALYSIS_CACHE[
            repository_name
        ] = result

        print(
            "✅ GEMINI ANALYSIS SUCCESSFUL",
            flush=True
        )

        return jsonify({
            "success": True,
            "analysis": result
        })

    except Exception as exc:

        import traceback

        traceback.print_exc()

        print(
            f"❌ GITORA AI ERROR: {exc}",
            flush=True
        )

        return jsonify({
            "success": False,
            "error": (
                "Gitora AI error: "
                f"{str(exc)}"
            )
        }), 503


# ============================================================
# REBUILD OPTIONS
# ============================================================

@main.route("/rebuild-options", methods=["POST"])
def rebuild_options():

    print(
        "🔥 GITORA /rebuild-options ROUTE REACHED",
        flush=True
    )

    try:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        repository = data.get(
            "repository"
        )

        repository_url = (
            data.get("repository_url")
            or data.get("repo_url")
            or ""
        ).strip()

        if isinstance(repository, str):

            repository_name = repository

            if repository_url:

                repository = get_repository(
                    repository_url
                )

            else:

                owner, repo_name = parse_github_url(
                    repository
                )

                if owner and repo_name:

                    repository = get_repository(
                        f"https://github.com/{owner}/{repo_name}"
                    )

        if not repository and repository_url:

            repository = get_repository(
                repository_url
            )

        if not isinstance(repository, dict):

            return jsonify({
                "success": False,
                "error": "Repository information is missing."
            }), 400

        repository = normalize_repository(
            repository
        )

        repository_name = get_repository_identifier(
            repository
        )

        if not repository_name:

            return jsonify({
                "success": False,
                "error": "Unable to identify repository."
            }), 400

        # ----------------------------------------------------
        # CHECK FULL ANALYSIS CACHE
        # ----------------------------------------------------

        cached_analysis = AI_ANALYSIS_CACHE.get(
            repository_name
        )

        if is_valid_ai_analysis(
            cached_analysis
        ):

            options = cached_analysis.get(
                "rebuild_options",
                []
            )

            if options:

                return jsonify({
                    "success": True,
                    "rebuild_options": options
                })

        # ----------------------------------------------------
        # LOAD SAVED FILES
        # ----------------------------------------------------

        saved_paths = get_saved_file_paths(
            repository_name
        )

        source_files = load_source_files(
            repository,
            saved_paths
        )

        if not source_files:

            return jsonify({
                "success": False,
                "error": (
                    "No saved files were found. "
                    "Please save files first."
                )
            }), 400

        # ----------------------------------------------------
        # DEDICATED REBUILD ANALYSIS
        # ----------------------------------------------------

        result = generate_rebuild_strategies(
            repository=repository,
            files=source_files
        )

        options = (
            result.get("rebuild_options", [])
            if isinstance(result, dict)
            else []
        )

        return jsonify({
            "success": True,
            "rebuild_options": options
        })

    except Exception as exc:

        import traceback

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": (
                "Gitora AI error: "
                f"{str(exc)}"
            )
        }), 503


# ============================================================
# ANALYZE SINGLE FILE
# ============================================================

@main.route("/analyze-file", methods=["POST"])
def analyze_file():

    print(
        "🔥 GITORA /analyze-file ROUTE REACHED",
        flush=True
    )

    try:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        repository = data.get(
            "repository"
        )

        repository_url = (
            data.get("repository_url")
            or data.get("repo_url")
            or ""
        ).strip()

        file_path = (
            data.get("file_path")
            or data.get("path")
            or data.get("file")
            or ""
        ).strip()

        if isinstance(repository, str):

            if repository_url:

                repository = get_repository(
                    repository_url
                )

            else:

                owner, repo_name = parse_github_url(
                    repository
                )

                if owner and repo_name:

                    repository = get_repository(
                        f"https://github.com/{owner}/{repo_name}"
                    )

        if not repository and repository_url:

            repository = get_repository(
                repository_url
            )

        if not isinstance(repository, dict):

            return jsonify({
                "success": False,
                "error": "Repository information is missing."
            }), 400

        repository = normalize_repository(
            repository
        )

        repository_name = get_repository_identifier(
            repository
        )

        if not file_path:

            return jsonify({
                "success": False,
                "error": "File path is required."
            }), 400

        # ----------------------------------------------------
        # VERIFY FILE IS SAVED
        # ----------------------------------------------------

        saved_paths = get_saved_file_paths(
            repository_name
        )

        if file_path not in saved_paths:

            return jsonify({
                "success": False,
                "error": (
                    "This file has not been saved. "
                    "Please save the file before analyzing it."
                )
            }), 400

        # ----------------------------------------------------
        # CHECK FULL ANALYSIS CACHE
        # ----------------------------------------------------

        cached_analysis = AI_ANALYSIS_CACHE.get(
            repository_name
        )

        if is_valid_ai_analysis(
            cached_analysis
        ):

            for item in cached_analysis.get(
                "file_analysis",
                []
            ):

                if not isinstance(item, dict):
                    continue

                cached_path = (
                    item.get("file")
                    or item.get("path")
                    or ""
                )

                if cached_path == file_path:

                    return jsonify({
                        "success": True,
                        "analysis": item
                    })

        # ----------------------------------------------------
        # LOAD FILE FROM GITHUB
        # ----------------------------------------------------

        source_files = load_source_files(
            repository,
            [file_path]
        )

        if not source_files:

            return jsonify({
                "success": False,
                "error": "Unable to load the selected file."
            }), 404

        content = source_files[0].get(
            "content",
            ""
        )

        # ----------------------------------------------------
        # AI FILE ANALYSIS
        # ----------------------------------------------------

        result = analyze_single_file(
            repository=repository,
            file_path=file_path,
            content=content
        )

        if not isinstance(result, dict):

            return jsonify({
                "success": False,
                "error": (
                    "Gitora returned an invalid "
                    "file analysis."
                )
            }), 503

        print(
            f"✅ File analysis successful: {file_path}",
            flush=True
        )

        return jsonify({
            "success": True,
            "analysis": result
        })

    except Exception as exc:

        import traceback

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": (
                "Gitora AI error: "
                f"{str(exc)}"
            )
        }), 503


# ============================================================
# ASK GITORA AI
# ============================================================

@main.route("/ask-ai", methods=["POST"])
def ask_ai():

    print(
        "🔥 GITORA /ask-ai ROUTE REACHED",
        flush=True
    )

    try:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        repository = data.get(
            "repository"
        )

        repository_url = (
            data.get("repository_url")
            or data.get("repo_url")
            or ""
        ).strip()

        question = (
            data.get("question")
            or data.get("query")
            or ""
        ).strip()

        if not question:

            return jsonify({
                "success": False,
                "error": "Please enter a question."
            }), 400

        # ----------------------------------------------------
        # LOAD REPOSITORY
        # ----------------------------------------------------

        if isinstance(repository, str):

            if repository_url:

                repository = get_repository(
                    repository_url
                )

            else:

                owner, repo_name = parse_github_url(
                    repository
                )

                if owner and repo_name:

                    repository = get_repository(
                        f"https://github.com/{owner}/{repo_name}"
                    )

        if not repository and repository_url:

            repository = get_repository(
                repository_url
            )

        if not isinstance(repository, dict):

            return jsonify({
                "success": False,
                "error": "Repository information is missing."
            }), 400

        repository = normalize_repository(
            repository
        )

        repository_name = get_repository_identifier(
            repository
        )

        # ----------------------------------------------------
        # LOAD SAVED FILES
        # ----------------------------------------------------

        saved_paths = get_saved_file_paths(
            repository_name
        )

        source_files = load_source_files(
            repository,
            saved_paths
        )

        if not source_files:

            return jsonify({
                "success": False,
                "error": (
                    "No saved files were found. "
                    "Please save files first."
                )
            }), 400

        # ----------------------------------------------------
        # ASK AI
        # ----------------------------------------------------

        answer = answer_repository_question(
            repository=repository,
            files=source_files,
            question=question
        )

        if not answer:

            return jsonify({
                "success": False,
                "error": "Gitora AI returned an empty answer."
            }), 503

        return jsonify({
            "success": True,
            "answer": answer
        })

    except Exception as exc:

        import traceback

        traceback.print_exc()

        print(
            f"❌ ASK AI ERROR: {exc}",
            flush=True
        )

        return jsonify({
            "success": False,
            "error": (
                "Gitora AI error: "
                f"{str(exc)}"
            )
        }), 503


# ============================================================
# DOWNLOAD PDF REPORT
# ============================================================

@main.route("/download-report", methods=["POST"])
def download_report():

    print(
        "🔥 GITORA /download-report ROUTE REACHED",
        flush=True
    )

    try:

        data = (
            request.get_json(
                silent=True
            )
            or {}
        )

        repository = data.get(
            "repository"
        )

        repository_url = (
            data.get("repository_url")
            or data.get("repo_url")
            or ""
        ).strip()

        supplied_analysis = data.get(
            "ai_analysis"
        ) or data.get(
            "analysis"
        )

        # ----------------------------------------------------
        # LOAD REPOSITORY
        # ----------------------------------------------------

        if isinstance(repository, str):

            if repository_url:

                repository = get_repository(
                    repository_url
                )

            else:

                owner, repo_name = parse_github_url(
                    repository
                )

                if owner and repo_name:

                    repository = get_repository(
                        f"https://github.com/{owner}/{repo_name}"
                    )

        if not repository and repository_url:

            repository = get_repository(
                repository_url
            )

        if not isinstance(repository, dict):

            return jsonify({
                "success": False,
                "error": "Repository information is missing."
            }), 400

        repository = normalize_repository(
            repository
        )

        repository_name = get_repository_identifier(
            repository
        )

        # ----------------------------------------------------
        # LOAD SAVED FILES
        # ----------------------------------------------------

        saved_paths = get_saved_file_paths(
            repository_name
        )

        source_files = load_source_files(
            repository,
            saved_paths
        )

        if not source_files:

            return jsonify({
                "success": False,
                "error": (
                    "No saved files were found. "
                    "Please save files first."
                )
            }), 400

        # ----------------------------------------------------
        # USE SUPPLIED ANALYSIS
        # ----------------------------------------------------

        analysis = None

        if is_valid_ai_analysis(
            supplied_analysis
        ):

            analysis = supplied_analysis

        # ----------------------------------------------------
        # USE CACHE
        # ----------------------------------------------------

        if analysis is None:

            cached_analysis = AI_ANALYSIS_CACHE.get(
                repository_name
            )

            if is_valid_ai_analysis(
                cached_analysis
            ):

                analysis = cached_analysis

        # ----------------------------------------------------
        # GENERATE ANALYSIS IF NECESSARY
        # ----------------------------------------------------

        if analysis is None:

            print(
                "🔥 Generating AI analysis for PDF...",
                flush=True
            )

            analysis = analyze_repository(
                repository=repository,
                files=source_files
            )

            if not is_valid_ai_analysis(
                analysis
            ):

                return jsonify({
                    "success": False,
                    "error": (
                        "Unable to generate the AI "
                        "analysis required for the PDF."
                    )
                }), 503

            AI_ANALYSIS_CACHE[
                repository_name
            ] = analysis

        # ----------------------------------------------------
        # GENERATE PDF
        # ----------------------------------------------------

        pdf_buffer = generate_repository_pdf(
            repository=repository,
            source_files=source_files,
            ai_analysis=analysis
        )

        if pdf_buffer is None:

            return jsonify({
                "success": False,
                "error": "Unable to generate PDF report."
            }), 500

        filename = (
            repository.get("name")
            or "gitora"
        )

        filename = (
            f"{filename}_Gitora_Report.pdf"
        )

        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )

    except Exception as exc:

        import traceback

        traceback.print_exc()

        print(
            f"❌ PDF ERROR: {exc}",
            flush=True
        )

        return jsonify({
            "success": False,
            "error": (
                "Gitora PDF generation failed: "
                f"{str(exc)}"
            )
        }), 500


# ============================================================
# GEMINI HEALTH CHECK
# ============================================================

@main.route("/ai-health", methods=["GET"])
def ai_health():

    print(
        "🔥 GITORA /ai-health ROUTE REACHED",
        flush=True
    )

    if not GEMINI_API_KEY:

        return jsonify({
            "success": False,
            "gemini_key": False,
            "model": MODEL,
            "error": (
                "GEMINI_API_KEY is missing "
                "from the Render environment."
            )
        }), 500

    try:

        client = get_gemini_client()

        interaction = client.interactions.create(
            model=MODEL,
            input="Reply with exactly: GITORA_AI_OK",
            generation_config={
                "max_output_tokens": 20
            }
        )

        output = getattr(
            interaction,
            "output_text",
            ""
        )

        return jsonify({
            "success": True,
            "gemini_key": True,
            "model": MODEL,
            "response": output
        })

    except Exception as exc:

        import traceback

        traceback.print_exc()

        return jsonify({
            "success": False,
            "gemini_key": True,
            "model": MODEL,
            "error": str(exc)
        }), 503