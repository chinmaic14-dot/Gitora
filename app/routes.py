from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    send_file
)

from app.services.github_service import (
    get_repository_info,
    get_repository_files,
    get_file_content,
    categorize_file
)

from app.services.ai_service import (
    analyze_repository,
    analyze_single_file,
    answer_repository_question
)

from app.services.pdf_service import (
    generate_repository_pdf
)

from app.models import (
    db,
    SavedFileSelection
)


# =====================================================
# BLUEPRINT
# =====================================================

main = Blueprint("main", __name__)


# =====================================================
# AI CACHE
# =====================================================

AI_ANALYSIS_CACHE = {}


# =====================================================
# AI VALIDATION
# =====================================================

def is_valid_ai_analysis(analysis):

    if not isinstance(analysis, dict):
        return False

    project_summary = str(
        analysis.get(
            "project_summary",
            ""
        )
    ).strip()

    if not project_summary:
        return False

    failed_messages = [
        "gemini could not generate repository analysis",
        "gemini could not analyze repository",
        "ai analysis unavailable",
        "analysis unavailable",
        "couldn't analyze",
        "could not analyze",
        "failed to analyze",
        "unable to analyze",
        "error generating analysis"
    ]

    lowered = project_summary.lower()

    for message in failed_messages:

        if message in lowered:
            return False

    return True


# =====================================================
# GET SAVED FILE PATHS
# =====================================================

def get_saved_file_paths(repository_name):

    selections = SavedFileSelection.query.filter_by(
        repository=repository_name
    ).all()

    return [
        item.file_path
        for item in selections
        if item.file_path
    ]


# =====================================================
# LOAD SOURCE FILES
# =====================================================

def load_source_files(
    repository,
    file_paths
):

    source_files = []

    if not repository:
        return source_files

    for file_path in file_paths:

        try:

            content = get_file_content(
                repository["owner"],
                repository["repo"],
                file_path,
                repository["default_branch"]
            )

            if content is not None:

                source_files.append({
                    "path": file_path,
                    "content": content
                })

        except Exception as error:

            print(
                "❌ FILE LOAD ERROR:",
                file_path,
                type(error).__name__,
                str(error)
            )

    return source_files


# =====================================================
# HOME
# =====================================================

@main.route(
    "/",
    methods=["GET"]
)
def home():

    return render_template(
        "index.html"
    )


# =====================================================
# ANALYZE REPOSITORY
# =====================================================

@main.route(
    "/analyze",
    methods=["POST"]
)
def analyze():

    print(
        "\n🔥 GITORA /analyze ROUTE REACHED"
    )

    repo_url = request.form.get(
        "repo_url",
        ""
    ).strip()

    print(
        "Repository URL:",
        repo_url
    )

    if not repo_url:

        return render_template(
            "index.html",
            error="Please enter a GitHub repository URL."
        )

    try:

        # -------------------------------------------------
        # GET REPOSITORY INFORMATION
        # -------------------------------------------------

        print(
            "Loading repository information..."
        )

        repository = get_repository_info(
            repo_url
        )

        print(
            "Repository loaded:",
            repository
        )

        if not repository:

            return render_template(
                "index.html",
                error="Unable to load GitHub repository."
            )

        # -------------------------------------------------
        # GET REPOSITORY FILES
        # -------------------------------------------------

        print(
            "Loading repository files..."
        )

        files = get_repository_files(
            repository["owner"],
            repository["repo"],
            repository["default_branch"]
        )

        print(
            "Repository files:",
            len(files)
        )

        # -------------------------------------------------
        # SAVED FILES
        # -------------------------------------------------

        repository_name = repository.get(
            "full_name"
        )

        saved_paths = get_saved_file_paths(
            repository_name
        )

        print(
            "Saved files:",
            saved_paths
        )

        # -------------------------------------------------
        # LOAD SOURCE FILES
        # -------------------------------------------------

        source_files = load_source_files(
            repository,
            saved_paths
        )

        print(
            "Source files loaded:",
            len(source_files)
        )

        # -------------------------------------------------
        # RENDER ANALYSIS PAGE
        # -------------------------------------------------

        return render_template(
            "analysis.html",
            repository=repository,
            files=files or [],
            source_files=source_files,
            ai_analysis=None
        )

    except ValueError as error:

        print(
            "❌ ANALYZE VALUE ERROR:",
            error
        )

        return render_template(
            "index.html",
            error=str(error)
        )

    except Exception as error:

        print(
            "❌ ANALYZE ERROR:",
            type(error).__name__,
            str(error)
        )

        return render_template(
            "index.html",
            error="Unable to analyze this GitHub repository."
        )

    finally:

        db.session.remove()


# =====================================================
# SAVE SELECTED FILES
# =====================================================

@main.route(
    "/save-files",
    methods=["POST"]
)
def save_files():

    print(
        "\n🔥 GITORA /save-files ROUTE REACHED"
    )

    repository_name = request.form.get(
        "repository",
        ""
    ).strip()

    selected_files = request.form.getlist(
        "selected_files"
    )

    print(
        "Repository:",
        repository_name
    )

    print(
        "Selected files:",
        selected_files
    )

    if not repository_name:

        return jsonify({
            "success": False,
            "error": "Repository is required."
        }), 400

    try:

        # -------------------------------------------------
        # REMOVE OLD SELECTIONS
        # -------------------------------------------------

        SavedFileSelection.query.filter_by(
            repository=repository_name
        ).delete()

        # -------------------------------------------------
        # SAVE NEW SELECTIONS
        # -------------------------------------------------

        for file_path in selected_files:

            if not file_path:
                continue

            db.session.add(
                SavedFileSelection(
                    repository=repository_name,
                    file_path=file_path
                )
            )

        db.session.commit()

        # -------------------------------------------------
        # INVALIDATE OLD AI CACHE
        # -------------------------------------------------

        AI_ANALYSIS_CACHE.pop(
            repository_name,
            None
        )

        # -------------------------------------------------
        # LOAD REPOSITORY AGAIN
        # -------------------------------------------------

        repository = get_repository_info(
            "https://github.com/"
            + repository_name
        )

        if not repository:

            return jsonify({
                "success": False,
                "error": "Unable to load repository."
            }), 400

        files = get_repository_files(
            repository["owner"],
            repository["repo"],
            repository["default_branch"]
        )

        source_files = load_source_files(
            repository,
            selected_files
        )

        print(
            "Saved successfully."
        )

        return render_template(
            "analysis.html",
            repository=repository,
            files=files or [],
            source_files=source_files,
            ai_analysis=None
        )

    except Exception as error:

        db.session.rollback()

        print(
            "❌ SAVE FILES ERROR:",
            type(error).__name__,
            str(error)
        )

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500

    finally:

        db.session.remove()


# =====================================================
# FULL AI ANALYSIS
# =====================================================

@main.route(
    "/ai-analyze",
    methods=["POST"]
)
def ai_analyze():

    print(
        "\n🔥 GITORA /ai-analyze ROUTE REACHED"
    )

    repository_name = request.form.get(
        "repository",
        ""
    ).strip()

    print(
        "Repository:",
        repository_name
    )

    if not repository_name:

        return jsonify({
            "success": False,
            "error": "Repository is required."
        }), 400

    try:

        # -------------------------------------------------
        # CHECK BROWSER FILES
        # -------------------------------------------------

        selected_files = request.form.getlist(
            "selected_files"
        )

        print(
            "Files received directly from browser:",
            selected_files
        )

        # -------------------------------------------------
        # FALL BACK TO DATABASE
        # -------------------------------------------------

        if not selected_files:

            print(
                "⚠️ No files received from browser."
            )

            selected_files = get_saved_file_paths(
                repository_name
            )

            print(
                "Files loaded from database:",
                selected_files
            )

        if not selected_files:

            return jsonify({
                "success": False,
                "error": "Please select at least one file to analyze."
            }), 400

        # -------------------------------------------------
        # CACHE CHECK
        # -------------------------------------------------

        cached_analysis = AI_ANALYSIS_CACHE.get(
            repository_name
        )

        if is_valid_ai_analysis(
            cached_analysis
        ):

            print(
                "✅ USING CACHED AI ANALYSIS"
            )

            return jsonify({
                "success": True,
                "analysis": cached_analysis
            })

        # Remove invalid cached result.

        if cached_analysis is not None:

            print(
                "⚠️ Removing invalid AI cache."
            )

            AI_ANALYSIS_CACHE.pop(
                repository_name,
                None
            )

        # -------------------------------------------------
        # LOAD REPOSITORY
        # -------------------------------------------------

        print(
            "Loading repository information..."
        )

        repository = get_repository_info(
            "https://github.com/"
            + repository_name
        )

        if not repository:

            return jsonify({
                "success": False,
                "error": "Unable to load GitHub repository."
            }), 400

        # -------------------------------------------------
        # LOAD SOURCE FILES
        # -------------------------------------------------

        source_files = load_source_files(
            repository,
            selected_files
        )

        print(
            "Source files loaded:",
            len(source_files)
        )

        if not source_files:

            return jsonify({
                "success": False,
                "error": "Unable to load the selected repository files."
            }), 400

        # -------------------------------------------------
        # GEMINI
        # -------------------------------------------------

        print(
            "\n🔥 SENDING REQUEST TO GEMINI"
        )

        print(
            "Repository:",
            repository_name
        )

        print(
            "Files sent to Gemini:",
            len(source_files)
        )

        result = analyze_repository(
            repository=repository,
            files=source_files
        )

        print(
            "Gemini returned:",
            type(result).__name__
        )

        if not is_valid_ai_analysis(
            result
        ):

            print(
                "❌ AI ANALYSIS FAILED"
            )

            return jsonify({
                "success": False,
                "error": (
                    "Gemini could not analyze the repository "
                    "right now. Please try again."
                )
            }), 503

        # -------------------------------------------------
        # SAVE ONLY SUCCESSFUL ANALYSIS
        # -------------------------------------------------

        AI_ANALYSIS_CACHE[
            repository_name
        ] = result

        print(
            "✅ AI ANALYSIS SAVED TO CACHE"
        )

        print(
            "Rebuild options:",
            len(
                result.get(
                    "rebuild_options",
                    []
                )
            )
        )

        print(
            "🔥 FULL AI ANALYSIS COMPLETED"
        )

        return jsonify({
            "success": True,
            "analysis": result
        })

    except ValueError as error:

        print(
            "❌ AI ANALYSIS VALUE ERROR:",
            error
        )

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500

    except Exception as error:

        print(
            "❌ AI ANALYSIS ERROR:",
            type(error).__name__,
            str(error)
        )

        return jsonify({
            "success": False,
            "error": (
                "Gemini could not analyze the repository "
                "right now. Please try again."
            )
        }), 500

    finally:

        db.session.remove()


# =====================================================
# REBUILD OPTIONS
# =====================================================

@main.route(
    "/rebuild-options",
    methods=["POST"]
)
def rebuild_options():

    print(
        "\n🔥 GITORA /rebuild-options ROUTE REACHED"
    )

    repository_name = request.form.get(
        "repository",
        ""
    ).strip()

    if not repository_name:

        return jsonify({
            "success": False,
            "error": "Repository is required."
        }), 400

    try:

        cached_analysis = AI_ANALYSIS_CACHE.get(
            repository_name
        )

        if is_valid_ai_analysis(
            cached_analysis
        ):

            return jsonify({
                "success": True,
                "rebuild_options":
                    cached_analysis.get(
                        "rebuild_options",
                        []
                    )
            })

        if cached_analysis is not None:

            AI_ANALYSIS_CACHE.pop(
                repository_name,
                None
            )

        # -------------------------------------------------
        # LOAD SAVED FILES
        # -------------------------------------------------

        selected_files = get_saved_file_paths(
            repository_name
        )

        if not selected_files:

            return jsonify({
                "success": False,
                "error": "No saved files found."
            }), 400

        repository = get_repository_info(
            "https://github.com/"
            + repository_name
        )

        source_files = load_source_files(
            repository,
            selected_files
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
                    "Gemini could not generate "
                    "rebuild options right now."
                )
            }), 503

        AI_ANALYSIS_CACHE[
            repository_name
        ] = result

        return jsonify({
            "success": True,
            "rebuild_options":
                result.get(
                    "rebuild_options",
                    []
                )
        })

    except Exception as error:

        print(
            "❌ REBUILD OPTIONS ERROR:",
            type(error).__name__,
            str(error)
        )

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500

    finally:

        db.session.remove()


# =====================================================
# ANALYZE SINGLE FILE
# =====================================================

@main.route(
    "/analyze-file",
    methods=["POST"]
)
def analyze_file():

    print(
        "\n🔥 GITORA /analyze-file ROUTE REACHED"
    )

    repository_name = request.form.get(
        "repository",
        ""
    ).strip()

    file_path = request.form.get(
        "file_path",
        ""
    ).strip()

    if not repository_name:

        return jsonify({
            "success": False,
            "error": "Repository is required."
        }), 400

    if not file_path:

        return jsonify({
            "success": False,
            "error": "File path is required."
        }), 400

    try:

        # -------------------------------------------------
        # CHECK SAVED FILES
        # -------------------------------------------------

        saved_paths = get_saved_file_paths(
            repository_name
        )

        if file_path not in saved_paths:

            return jsonify({
                "success": False,
                "error": (
                    "Please save/select this file "
                    "before analyzing it."
                )
            }), 400

        # -------------------------------------------------
        # CHECK FULL AI CACHE
        # -------------------------------------------------

        cached_analysis = AI_ANALYSIS_CACHE.get(
            repository_name
        )

        if is_valid_ai_analysis(
            cached_analysis
        ):

            file_analysis = cached_analysis.get(
                "file_analysis",
                []
            )

            for item in file_analysis:

                if item.get("file") == file_path:

                    return jsonify({
                        "success": True,
                        "analysis": item
                    })

        # -------------------------------------------------
        # LOAD REPOSITORY
        # -------------------------------------------------

        repository = get_repository_info(
            "https://github.com/"
            + repository_name
        )

        if not repository:

            return jsonify({
                "success": False,
                "error": "Unable to load repository."
            }), 400

        # -------------------------------------------------
        # LOAD FILES
        # -------------------------------------------------

        source_files = load_source_files(
            repository,
            saved_paths
        )

        if not source_files:

            return jsonify({
                "success": False,
                "error": "Unable to load selected files."
            }), 400

        # -------------------------------------------------
        # AI
        # -------------------------------------------------

        result = analyze_single_file(
            repository=repository,
            files=source_files,
            selected_file=file_path
        )

        if not isinstance(
            result,
            dict
        ):

            return jsonify({
                "success": False,
                "error": "AI could not analyze this file."
            }), 503

        return jsonify({
            "success": True,
            "analysis": result
        })

    except Exception as error:

        print(
            "❌ SINGLE FILE ANALYSIS ERROR:",
            type(error).__name__,
            str(error)
        )

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500

    finally:

        db.session.remove()


# =====================================================
# ASK AI
# =====================================================

@main.route(
    "/ask-ai",
    methods=["POST"]
)
def ask_ai():

    print(
        "\n🔥 GITORA /ask-ai ROUTE REACHED"
    )

    repository_name = request.form.get(
        "repository",
        ""
    ).strip()

    question = request.form.get(
        "question",
        ""
    ).strip()

    if not repository_name:

        return jsonify({
            "success": False,
            "error": "Repository is required."
        }), 400

    if not question:

        return jsonify({
            "success": False,
            "error": "Please enter a question."
        }), 400

    try:

        selected_files = get_saved_file_paths(
            repository_name
        )

        if not selected_files:

            return jsonify({
                "success": False,
                "error": "No saved files found."
            }), 400

        repository = get_repository_info(
            "https://github.com/"
            + repository_name
        )

        if not repository:

            return jsonify({
                "success": False,
                "error": "Unable to load repository."
            }), 400

        source_files = load_source_files(
            repository,
            selected_files
        )

        if not source_files:

            return jsonify({
                "success": False,
                "error": "Unable to load selected files."
            }), 400

        answer = answer_repository_question(
            question=question,
            repository=repository,
            files=source_files
        )

        return jsonify({
            "success": True,
            "answer": answer
        })

    except Exception as error:

        print(
            "❌ ASK AI ERROR:",
            type(error).__name__,
            str(error)
        )

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500

    finally:

        db.session.remove()


# =====================================================
# DOWNLOAD PDF REPORT
# =====================================================

@main.route(
    "/download-report",
    methods=["POST"]
)
def download_report():

    print(
        "\n🔥 GITORA DOWNLOAD REPORT"
    )

    repository_name = request.form.get(
        "repository",
        ""
    ).strip()

    print(
        "Repository:",
        repository_name
    )

    if not repository_name:

        return jsonify({
            "success": False,
            "error": "Repository is required."
        }), 400

    try:

        # -------------------------------------------------
        # LOAD REPOSITORY
        # -------------------------------------------------

        repository = get_repository_info(
            "https://github.com/"
            + repository_name
        )

        if not repository:

            return jsonify({
                "success": False,
                "error": "Unable to load repository."
            }), 400

        # -------------------------------------------------
        # LOAD SAVED FILES
        # -------------------------------------------------

        selected_files = get_saved_file_paths(
            repository_name
        )

        if not selected_files:

            return jsonify({
                "success": False,
                "error": (
                    "Please select and save files "
                    "before generating the PDF."
                )
            }), 400

        source_files = load_source_files(
            repository,
            selected_files
        )

        if not source_files:

            return jsonify({
                "success": False,
                "error": "Unable to load selected files."
            }), 400

        # -------------------------------------------------
        # GET AI ANALYSIS FROM CACHE
        # -------------------------------------------------

        analysis = AI_ANALYSIS_CACHE.get(
            repository_name
        )

        if is_valid_ai_analysis(
            analysis
        ):

            print(
                "✅ Using cached AI analysis for PDF."
            )

        else:

            # Remove invalid cache.

            AI_ANALYSIS_CACHE.pop(
                repository_name,
                None
            )

            print(
                "⚠️ No valid AI analysis found."
            )

            print(
                "🔥 Generating AI analysis for PDF..."
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
                        "Gemini could not analyze the "
                        "repository, so the PDF cannot "
                        "be generated right now."
                    )
                }), 503

            AI_ANALYSIS_CACHE[
                repository_name
            ] = analysis

        # -------------------------------------------------
        # GENERATE PDF
        # -------------------------------------------------

        print(
            "🔥 Generating repository PDF..."
        )

        pdf_buffer = generate_repository_pdf(
            repository=repository,
            source_files=source_files,
            ai_analysis=analysis
        )

        if not pdf_buffer:

            raise ValueError(
                "PDF generator returned no data."
            )

        # -------------------------------------------------
        # SEND PDF
        # -------------------------------------------------

        filename = (
            repository["name"]
            + "_Gitora_Report.pdf"
        )

        print(
            "✅ PDF GENERATED:",
            filename
        )

        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=filename,
            mimetype="application/pdf"
        )

    except ValueError as error:

        print(
            "❌ DOWNLOAD REPORT VALUE ERROR:",
            error
        )

        return jsonify({
            "success": False,
            "error": str(error)
        }), 500

    except Exception as error:

        print(
            "\n❌ DOWNLOAD REPORT ERROR"
        )

        print(
            "ERROR TYPE:",
            type(error).__name__
        )

        print(
            "ERROR:",
            repr(error)
        )

        return jsonify({
            "success": False,
            "error": (
                "Unable to generate the PDF report."
            )
        }), 500

    finally:

        db.session.remove()
        