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
    get_repository_info,
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
# REPOSITORY HELPERS
# ============================================================

def get_repository_identifier(repository):
    """
    Return the stable database/cache identifier:
    owner/repository
    """

    if not isinstance(repository, dict):
        return ""

    full_name = repository.get("full_name")

    if full_name:
        return str(full_name).strip()

    owner = repository.get("owner", "")
    repo = repository.get("repo", "")

    if isinstance(owner, dict):
        owner = owner.get("login", "")

    if owner and repo:
        return f"{owner}/{repo}"

    name = repository.get("name", "")

    return str(name).strip()


def parse_repository_input(repository_value):
    """
    Accept either:

    https://github.com/owner/repository
    owner/repository

    and return:

    owner, repository
    """

    value = (repository_value or "").strip()

    if not value:
        return None, None

    # --------------------------------------------------------
    # Full GitHub URL
    # --------------------------------------------------------

    if "github.com" in value.lower():

        parsed = urlparse(value)

        parts = [
            part.strip()
            for part in parsed.path.split("/")
            if part.strip()
        ]

    # --------------------------------------------------------
    # owner/repository
    # --------------------------------------------------------

    else:

        parts = [
            part.strip()
            for part in value.split("/")
            if part.strip()
        ]

    if len(parts) < 2:
        return None, None

    owner = parts[0]
    repo = parts[1]

    if repo.endswith(".git"):
        repo = repo[:-4]

    return owner, repo


def load_repository(repository_value):
    """
    Load repository information from either a GitHub URL
    or owner/repository.
    """

    owner, repo = parse_repository_input(
        repository_value
    )

    if not owner or not repo:
        return None

    repository_url = (
        f"https://github.com/{owner}/{repo}"
    )

    return get_repository_info(
        repository_url
    )


def get_repository_owner(repository):
    owner = repository.get("owner", "")

    if isinstance(owner, dict):
        return owner.get("login", "")

    return owner or ""


def get_repository_name(repository):
    return (
        repository.get("repo")
        or repository.get("name")
        or ""
    )


def get_repository_branch(repository):
    return (
        repository.get("default_branch")
        or "main"
    )


# ============================================================
# SAVED FILE HELPERS
# ============================================================

def get_saved_file_paths(repository_name):

    if not repository_name:
        return []

    try:

        saved = (
            SavedFileSelection.query
            .filter_by(
                repository=repository_name
            )
            .all()
        )

        paths = []

        for item in saved:

            path = getattr(
                item,
                "file_path",
                None
            )

            if path:
                paths.append(path)

        return paths

    except Exception as exc:

        print(
            f"⚠️ DATABASE READ ERROR: {exc}",
            flush=True
        )

        return []


def load_source_files(repository, file_paths):

    source_files = []

    if not isinstance(repository, dict):
        return source_files

    owner = get_repository_owner(
        repository
    )

    repo_name = get_repository_name(
        repository
    )

    branch = get_repository_branch(
        repository
    )

    if not owner or not repo_name:
        return source_files

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
                f"✅ GITHUB FILE LOADED: {path}",
                flush=True
            )

        except Exception as exc:

            print(
                f"⚠️ FAILED LOADING FILE {path}: {exc}",
                flush=True
            )

    return source_files


# ============================================================
# AI VALIDATION
# ============================================================

def is_valid_ai_analysis(analysis):

    if not isinstance(analysis, dict):
        return False

    if analysis.get("project_summary"):
        return True

    if analysis.get("technology_stack"):
        return True

    if analysis.get("file_analysis"):
        return True

    if analysis.get("architecture"):
        return True

    return False


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

@main.route(
    "/analyze",
    methods=["GET", "POST"]
)
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
        # REPOSITORY
        # ----------------------------------------------------

        repository = get_repository_info(
            repository_url
        )

        if not repository:

            return render_template(
                "index.html",
                error=(
                    "Unable to load GitHub repository."
                )
            )

        print(
            f"Repository loaded: {repository}",
            flush=True
        )

        repository_name = (
            get_repository_identifier(
                repository
            )
        )

        # ----------------------------------------------------
        # FILE TREE
        # ----------------------------------------------------

        owner = get_repository_owner(
            repository
        )

        repo_name = get_repository_name(
            repository
        )

        branch = get_repository_branch(
            repository
        )

        print(
            "Loading repository files...",
            flush=True
        )

        files = get_repository_files(
            owner,
            repo_name,
            branch
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

        saved_file_paths = (
            get_saved_file_paths(
                repository_name
            )
        )

        print(
            f"Saved files: {saved_file_paths}",
            flush=True
        )

        # ----------------------------------------------------
        # SOURCE FILES
        # ----------------------------------------------------

        source_files = load_source_files(
            repository,
            saved_file_paths
        )

        print(
            f"Source files loaded: "
            f"{len(source_files)}",
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
            error=(
                f"Unable to analyze repository: {exc}"
            )
        )


# ============================================================
# SAVE SELECTED FILES
# ============================================================

@main.route(
    "/save-files",
    methods=["POST"]
)
def save_files():

    print(
        "🔥 GITORA /save-files ROUTE REACHED",
        flush=True
    )

    try:

        # ----------------------------------------------------
        # READ REQUEST
        # ----------------------------------------------------

        if request.is_json:

            data = (
                request.get_json(
                    silent=True
                )
                or {}
            )

            repository_value = (
                data.get("repository_url")
                or data.get("repo_url")
                or data.get("repository")
                or ""
            )

            selected_files = (
                data.get("files")
                or data.get("selected_files")
                or []
            )

        else:

            repository_value = (
                request.form.get("repository_url")
                or request.form.get("repo_url")
                or request.form.get("repository")
                or request.form.get("url")
                or ""
            )

            selected_files = (
                request.form.getlist("files")
                or request.form.getlist(
                    "selected_files"
                )
            )

        repository_value = (
            repository_value or ""
        ).strip()

        print(
            f"Repository input: {repository_value}",
            flush=True
        )

        print(
            f"Selected files: {selected_files}",
            flush=True
        )

        # ----------------------------------------------------
        # LOAD REPOSITORY
        # ----------------------------------------------------

        repository = load_repository(
            repository_value
        )

        if not repository:

            return jsonify({
                "success": False,
                "error": (
                    "Unable to identify the "
                    "GitHub repository."
                )
            }), 400

        repository_name = (
            get_repository_identifier(
                repository
            )
        )

        # ----------------------------------------------------
        # DELETE OLD SELECTIONS
        # ----------------------------------------------------

        SavedFileSelection.query.filter_by(
            repository=repository_name
        ).delete()

        # ----------------------------------------------------
        # SAVE NEW FILES
        # ----------------------------------------------------

        cleaned_files = []

        for path in selected_files:

            path = str(path).strip()

            if not path:
                continue

            if path in cleaned_files:
                continue

            cleaned_files.append(path)

            db.session.add(
                SavedFileSelection(
                    repository=repository_name,
                    file_path=path
                )
            )

        db.session.commit()

        # ----------------------------------------------------
        # CLEAR CACHE
        # ----------------------------------------------------

        AI_ANALYSIS_CACHE.pop(
            repository_name,
            None
        )

        print(
            "✅ Saved successfully.",
            flush=True
        )

        # ----------------------------------------------------
        # JSON
        # ----------------------------------------------------

        if request.is_json:

            return jsonify({
                "success": True,
                "repository": repository_name,
                "files": cleaned_files
            })

        # ----------------------------------------------------
        # RELOAD ANALYSIS PAGE
        # ----------------------------------------------------

        repository_url = (
            repository.get("url")
            or f"https://github.com/"
            f"{repository_name}"
        )

        return redirect(
            url_for(
                "main.analyze",
                repository_url=repository_url
            )
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

@main.route(
    "/ai-analyze",
    methods=["POST"]
)
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

        repository_value = (
            data.get("repository_url")
            or data.get("repo_url")
            or data.get("repository")
            or ""
        )

        repository = None

        # ----------------------------------------------------
        # REPOSITORY
        # ----------------------------------------------------

        if isinstance(
            repository_value,
            dict
        ):

            repository = repository_value

        else:

            repository = load_repository(
                repository_value
            )

        if not repository:

            return jsonify({
                "success": False,
                "error": (
                    "Repository information "
                    "is missing."
                )
            }), 400

        repository_name = (
            get_repository_identifier(
                repository
            )
        )

        if not repository_name:

            return jsonify({
                "success": False,
                "error": (
                    "Unable to identify repository."
                )
            }), 400

        print(
            f"Repository: {repository_name}",
            flush=True
        )

        # ----------------------------------------------------
        # FILES FROM BROWSER
        # ----------------------------------------------------

        browser_files = (
            data.get("files")
            or data.get("source_files")
            or []
        )

        source_files = []

        if browser_files:

            for file in browser_files:

                if not isinstance(
                    file,
                    dict
                ):
                    continue

                path = (
                    file.get("path")
                    or file.get("file")
                    or file.get("filename")
                )

                content = file.get(
                    "content"
                )

                # If content exists, use it.
                if path and content is not None:

                    source_files.append({
                        "path": path,
                        "content": str(content)
                    })

        # ----------------------------------------------------
        # DATABASE FALLBACK
        # ----------------------------------------------------

        if not source_files:

            saved_paths = (
                get_saved_file_paths(
                    repository_name
                )
            )

            print(
                f"Saved files: {saved_paths}",
                flush=True
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
                    "Please select and save at "
                    "least one file."
                )
            }), 400

        print(
            f"Source files loaded: "
            f"{len(source_files)}",
            flush=True
        )

        # ----------------------------------------------------
        # CACHE
        # ----------------------------------------------------

        cached_analysis = (
            AI_ANALYSIS_CACHE.get(
                repository_name
            )
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
                "analysis": cached_analysis,
                "cached": True
            })

        # ----------------------------------------------------
        # GEMINI
        # ----------------------------------------------------

        print(
            "🔥 SENDING REQUEST TO GEMINI",
            flush=True
        )

        result = analyze_repository(
            repository,
            source_files
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

        AI_ANALYSIS_CACHE[
            repository_name
        ] = result

        print(
            "✅ GEMINI ANALYSIS SUCCESSFUL",
            flush=True
        )

        return jsonify({
            "success": True,
            "analysis": result,
            "cached": False
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
            "error": str(exc)
        }), 503


# ============================================================
# REBUILD OPTIONS
# ============================================================

@main.route(
    "/rebuild-options",
    methods=["POST"]
)
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

        repository_value = (
            data.get("repository_url")
            or data.get("repo_url")
            or data.get("repository")
            or ""
        )

        repository = (
            repository_value
            if isinstance(
                repository_value,
                dict
            )
            else load_repository(
                repository_value
            )
        )

        if not repository:

            return jsonify({
                "success": False,
                "error": (
                    "Repository information "
                    "is missing."
                )
            }), 400

        repository_name = (
            get_repository_identifier(
                repository
            )
        )

        # ----------------------------------------------------
        # CACHE
        # ----------------------------------------------------

        cached = (
            AI_ANALYSIS_CACHE.get(
                repository_name
            )
        )

        if is_valid_ai_analysis(cached):

            options = cached.get(
                "rebuild_options",
                []
            )

            if options:

                return jsonify({
                    "success": True,
                    "rebuild_options": options,
                    "cached": True
                })

        # ----------------------------------------------------
        # FILES
        # ----------------------------------------------------

        saved_paths = (
            get_saved_file_paths(
                repository_name
            )
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
        # AI
        # ----------------------------------------------------

        result = generate_rebuild_strategies(
            repository,
            source_files
        )

        options = []

        if isinstance(result, dict):

            options = result.get(
                "rebuild_options",
                []
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
            "error": str(exc)
        }), 503


# ============================================================
# SINGLE FILE ANALYSIS
# ============================================================

@main.route(
    "/analyze-file",
    methods=["POST"]
)
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

        repository_value = (
            data.get("repository_url")
            or data.get("repo_url")
            or data.get("repository")
            or ""
        )

        file_path = (
            data.get("file_path")
            or data.get("path")
            or data.get("file")
            or ""
        ).strip()

        if not file_path:

            return jsonify({
                "success": False,
                "error": "File path is required."
            }), 400

        repository = (
            repository_value
            if isinstance(
                repository_value,
                dict
            )
            else load_repository(
                repository_value
            )
        )

        if not repository:

            return jsonify({
                "success": False,
                "error": (
                    "Repository information "
                    "is missing."
                )
            }), 400

        repository_name = (
            get_repository_identifier(
                repository
            )
        )

        # ----------------------------------------------------
        # SAVED CHECK
        # ----------------------------------------------------

        saved_paths = (
            get_saved_file_paths(
                repository_name
            )
        )

        if file_path not in saved_paths:

            return jsonify({
                "success": False,
                "error": (
                    "This file has not been saved. "
                    "Please save the file before "
                    "analyzing it."
                )
            }), 400

        # ----------------------------------------------------
        # CACHE
        # ----------------------------------------------------

        cached = (
            AI_ANALYSIS_CACHE.get(
                repository_name
            )
        )

        if is_valid_ai_analysis(cached):

            for item in cached.get(
                "file_analysis",
                []
            ):

                if not isinstance(
                    item,
                    dict
                ):
                    continue

                cached_path = (
                    item.get("file")
                    or item.get("path")
                    or ""
                )

                if cached_path == file_path:

                    return jsonify({
                        "success": True,
                        "analysis": item,
                        "cached": True
                    })

        # ----------------------------------------------------
        # LOAD FILE
        # ----------------------------------------------------

        source_files = load_source_files(
            repository,
            [file_path]
        )

        if not source_files:

            return jsonify({
                "success": False,
                "error": (
                    "Unable to load the "
                    "selected file."
                )
            }), 404

        content = source_files[0].get(
            "content",
            ""
        )

        # ----------------------------------------------------
        # AI
        # ----------------------------------------------------

        result = analyze_single_file(
            repository,
            file_path,
            content
        )

        if not isinstance(result, dict):

            return jsonify({
                "success": False,
                "error": (
                    "Gitora returned an invalid "
                    "file analysis."
                )
            }), 503

        return jsonify({
            "success": True,
            "analysis": result,
            "cached": False
        })

    except Exception as exc:

        import traceback

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 503


# ============================================================
# ASK GITORA AI
# ============================================================

@main.route(
    "/ask-ai",
    methods=["POST"]
)
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

        repository_value = (
            data.get("repository_url")
            or data.get("repo_url")
            or data.get("repository")
            or ""
        )

        question = (
            data.get("question")
            or data.get("query")
            or ""
        ).strip()

        if not question:

            return jsonify({
                "success": False,
                "error": (
                    "Please enter a question."
                )
            }), 400

        repository = (
            repository_value
            if isinstance(
                repository_value,
                dict
            )
            else load_repository(
                repository_value
            )
        )

        if not repository:

            return jsonify({
                "success": False,
                "error": (
                    "Repository information "
                    "is missing."
                )
            }), 400

        repository_name = (
            get_repository_identifier(
                repository
            )
        )

        saved_paths = (
            get_saved_file_paths(
                repository_name
            )
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

        answer = answer_repository_question(
            repository,
            source_files,
            question
        )

        if not answer:

            return jsonify({
                "success": False,
                "error": (
                    "Gitora AI returned "
                    "an empty answer."
                )
            }), 503

        return jsonify({
            "success": True,
            "answer": answer
        })

    except Exception as exc:

        import traceback

        traceback.print_exc()

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 503


# ============================================================
# DOWNLOAD PDF REPORT
# ============================================================

@main.route(
    "/download-report",
    methods=["POST"]
)
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

        repository_value = (
            data.get("repository_url")
            or data.get("repo_url")
            or data.get("repository")
            or ""
        )

        supplied_analysis = (
            data.get("ai_analysis")
            or data.get("analysis")
        )

        repository = (
            repository_value
            if isinstance(
                repository_value,
                dict
            )
            else load_repository(
                repository_value
            )
        )

        if not repository:

            return jsonify({
                "success": False,
                "error": (
                    "Repository information "
                    "is missing."
                )
            }), 400

        repository_name = (
            get_repository_identifier(
                repository
            )
        )

        saved_paths = (
            get_saved_file_paths(
                repository_name
            )
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
        # ANALYSIS
        # ----------------------------------------------------

        analysis = None

        if is_valid_ai_analysis(
            supplied_analysis
        ):

            analysis = supplied_analysis

        if analysis is None:

            cached = (
                AI_ANALYSIS_CACHE.get(
                    repository_name
                )
            )

            if is_valid_ai_analysis(cached):

                analysis = cached

        if analysis is None:

            print(
                "🔥 Generating AI analysis "
                "for PDF...",
                flush=True
            )

            analysis = analyze_repository(
                repository,
                source_files
            )

            if not is_valid_ai_analysis(
                analysis
            ):

                return jsonify({
                    "success": False,
                    "error": (
                        "Unable to generate the "
                        "AI analysis required "
                        "for the PDF."
                    )
                }), 503

            AI_ANALYSIS_CACHE[
                repository_name
            ] = analysis

        # ----------------------------------------------------
        # PDF
        # ----------------------------------------------------

        pdf_buffer = generate_repository_pdf(
            repository=repository,
            source_files=source_files,
            ai_analysis=analysis
        )

        if pdf_buffer is None:

            return jsonify({
                "success": False,
                "error": (
                    "Unable to generate "
                    "PDF report."
                )
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

        return jsonify({
            "success": False,
            "error": str(exc)
        }), 500


# ============================================================
# GEMINI HEALTH CHECK
# ============================================================

@main.route(
    "/ai-health",
    methods=["GET"]
)
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
            input=(
                "Reply with exactly: "
                "GITORA_AI_OK"
            ),
            generation_config={
                "max_output_tokens": 20
            }
        )

        output = getattr(
            interaction,
            "output_text",
            ""
        )

        if not output:

            return jsonify({
                "success": False,
                "gemini_key": True,
                "model": MODEL,
                "error": (
                    "Gemini returned "
                    "an empty response."
                )
            }), 503

        return jsonify({
            "success": True,
            "gemini_key": True,
            "model": MODEL,
            "response": output.strip()
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