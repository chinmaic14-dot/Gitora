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

main = Blueprint(
    "main",
    __name__
)


# =====================================================
# DATABASE SESSION CLEANUP
# =====================================================
#
# IMPORTANT:
# SQLAlchemy connections must be returned to the pool
# after every request.
#
# This is especially important because Gitora performs
# long-running AI and PDF operations.
#
# =====================================================

@main.teardown_app_request
def cleanup_database_session(exception=None):

    try:
        db.session.remove()

    except Exception as error:

        print(
            "DATABASE SESSION CLEANUP ERROR:",
            repr(error)
        )


# =====================================================
# HELPER: GET SAVED FILE PATHS
# =====================================================

def get_saved_file_paths(repository_name):

    """
    Reads saved file selections and immediately removes
    the SQLAlchemy session afterward.

    This prevents a database connection from remaining
    checked out while GitHub / AI / PDF operations run.
    """

    try:

        records = (
            SavedFileSelection.query
            .filter_by(
                repository=repository_name
            )
            .all()
        )

        return [
            record.file_path
            for record in records
        ]

    finally:

        # Return DB connection to pool immediately.
        db.session.remove()


# =====================================================
# HOME
# =====================================================

@main.route("/")
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

    repo_url = request.form.get(
        "repo_url",
        ""
    ).strip()

    if not repo_url:

        return render_template(
            "index.html",
            error="Please enter a GitHub repository URL."
        )

    try:

        repository = get_repository_info(
            repo_url
        )

        files = get_repository_files(
            repository["owner"],
            repository["repo"],
            repository["default_branch"]
        )

        categorized_files = []

        for file in files:

            categorized_files.append({

                "path": file["path"],

                "categories": categorize_file(
                    file["path"]
                )

            })

        # Get saved selections and immediately release DB.
        saved_files = get_saved_file_paths(
            repository["full_name"]
        )

        source_files = []

        for file_path in saved_files:

            content = get_file_content(

                repository["owner"],
                repository["repo"],
                file_path,
                repository["default_branch"]

            )

            if content is not None:

                source_files.append({

                    "path": file_path,

                    "content": content,

                    "categories": categorize_file(
                        file_path
                    )

                })

        return render_template(

            "analysis.html",

            repository=repository,

            files=files,

            categorized_files=categorized_files,

            source_files=source_files,

            saved_files=saved_files,

            ai_analysis=None

        )

    except ValueError as error:

        return render_template(

            "index.html",

            error=str(error)

        )

    except Exception as error:

        print(
            "ANALYSIS ERROR:",
            repr(error)
        )

        return render_template(

            "index.html",

            error=(
                "Something went wrong while "
                "analyzing the repository."
            )

        )


# =====================================================
# SAVE SELECTED FILES
# =====================================================

@main.route(
    "/save-files",
    methods=["POST"]
)
def save_files():

    repository = request.form.get(
        "repository",
        ""
    ).strip()

    selected_files = request.form.getlist(
        "selected_files"
    )

    if not repository:

        return redirect(
            url_for("main.home")
        )

    try:

        # -------------------------------------------------
        # Remove old selections
        # -------------------------------------------------

        SavedFileSelection.query.filter_by(
            repository=repository
        ).delete(
            synchronize_session=False
        )

        # -------------------------------------------------
        # Add new selections
        # -------------------------------------------------

        for file_path in selected_files:

            saved_file = SavedFileSelection(

                repository=repository,

                file_path=file_path

            )

            db.session.add(
                saved_file
            )

        db.session.commit()

        print(
            "FILES SAVED:",
            repository,
            selected_files
        )

    except Exception as error:

        db.session.rollback()

        print(
            "SAVE FILE ERROR:",
            repr(error)
        )

        return redirect(
            url_for("main.home")
        )

    finally:

        # Critical:
        # Release DB connection immediately.
        db.session.remove()

    # =================================================
    # RELOAD ANALYSIS PAGE
    # =================================================

    try:

        repository_url = (
            "https://github.com/"
            + repository
        )

        repository_info = get_repository_info(
            repository_url
        )

        files = get_repository_files(

            repository_info["owner"],

            repository_info["repo"],

            repository_info["default_branch"]

        )

        categorized_files = []

        for file in files:

            categorized_files.append({

                "path": file["path"],

                "categories": categorize_file(
                    file["path"]
                )

            })

        source_files = []

        for file_path in selected_files:

            content = get_file_content(

                repository_info["owner"],

                repository_info["repo"],

                file_path,

                repository_info["default_branch"]

            )

            if content is not None:

                source_files.append({

                    "path": file_path,

                    "content": content,

                    "categories": categorize_file(
                        file_path
                    )

                })

        return render_template(

            "analysis.html",

            repository=repository_info,

            files=files,

            categorized_files=categorized_files,

            source_files=source_files,

            saved_files=selected_files,

            ai_analysis=None

        )

    except Exception as error:

        print(
            "RETURN ANALYSIS ERROR:",
            repr(error)
        )

        return redirect(
            url_for("main.home")
        )

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

    try:

        repository_name = request.form.get(
            "repository",
            ""
        ).strip()

        if not repository_name:

            return jsonify({

                "success": False,

                "message":
                    "Repository information is missing."

            })

        # -------------------------------------------------
        # DATABASE OPERATION
        # -------------------------------------------------

        saved_files = get_saved_file_paths(
            repository_name
        )

        if not saved_files:

            return jsonify({

                "success": False,

                "message":
                    "Please select and save at least "
                    "one repository file."

            })

        # -------------------------------------------------
        # GITHUB OPERATION
        # -------------------------------------------------

        repository = get_repository_info(

            "https://github.com/"
            + repository_name

        )

        source_files = []

        for file_path in saved_files:

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

        if not source_files:

            return jsonify({

                "success": False,

                "message":
                    "Unable to load the selected files."

            })

        # -------------------------------------------------
        # AI OPERATION
        # -------------------------------------------------

        result = analyze_repository(

            repository=repository,

            files=source_files

        )

        if not isinstance(
            result,
            dict
        ):

            return jsonify({

                "success": False,

                "message":
                    "Gitora AI returned an invalid response."

            })

        return jsonify({

            "success": True,

            "analysis": result,

            "rebuild_options":
                result.get(
                    "rebuild_options",
                    []
                )

        })

    except Exception as error:

        print(
            "AI ANALYSIS ERROR:",
            repr(error)
        )

        return jsonify({

            "success": False,

            "message":
                "Gitora AI could not analyze the "
                "repository. Make sure Ollama is "
                "running and llama3.2 is installed."

        })

    finally:

        db.session.remove()


# =====================================================
# STEP 3
# THREE WAYS TO REBUILD
# =====================================================

@main.route(
    "/rebuild-options",
    methods=["POST"]
)
def rebuild_options():

    try:

        repository_name = request.form.get(
            "repository",
            ""
        ).strip()

        if not repository_name:

            return jsonify({

                "success": False,

                "message":
                    "Repository information is missing."

            })

        # -------------------------------------------------
        # DATABASE
        # -------------------------------------------------

        saved_files = get_saved_file_paths(
            repository_name
        )

        if not saved_files:

            return jsonify({

                "success": False,

                "message":
                    "Please select and save at least "
                    "one repository file first."

            })

        # -------------------------------------------------
        # GITHUB
        # -------------------------------------------------

        repository = get_repository_info(

            "https://github.com/"
            + repository_name

        )

        source_files = []

        for file_path in saved_files:

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

        if not source_files:

            return jsonify({

                "success": False,

                "message":
                    "Unable to load the selected files."

            })

        # -------------------------------------------------
        # AI
        # -------------------------------------------------

        analysis = analyze_repository(

            repository=repository,

            files=source_files

        )

        if not isinstance(
            analysis,
            dict
        ):

            return jsonify({

                "success": False,

                "message":
                    "Gitora AI returned an invalid analysis."

            })

        options = analysis.get(
            "rebuild_options",
            []
        )

        if not isinstance(
            options,
            list
        ):

            options = []

        options = options[:3]

        return jsonify({

            "success": True,

            "repository":
                repository.get(
                    "full_name",
                    repository_name
                ),

            "options": options,

            "count": len(options)

        })

    except Exception as error:

        print(
            "REBUILD OPTIONS ERROR:",
            repr(error)
        )

        return jsonify({

            "success": False,

            "message":
                "Gitora AI could not generate the "
                "three rebuild approaches."

        })

    finally:

        db.session.remove()


# =====================================================
# ANALYZE ONE FILE
# =====================================================

@main.route(
    "/analyze-file",
    methods=["POST"]
)
def analyze_file():

    try:

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

                "message":
                    "Repository information is missing."

            })

        if not file_path:

            return jsonify({

                "success": False,

                "message":
                    "File information is missing."

            })

        # -------------------------------------------------
        # DATABASE
        # -------------------------------------------------

        saved_files = get_saved_file_paths(
            repository_name
        )

        if file_path not in saved_files:

            return jsonify({

                "success": False,

                "message":
                    "This file has not been saved."

            })

        # -------------------------------------------------
        # GITHUB
        # -------------------------------------------------

        repository = get_repository_info(

            "https://github.com/"
            + repository_name

        )

        content = get_file_content(

            repository["owner"],
            repository["repo"],
            file_path,
            repository["default_branch"]

        )

        if content is None:

            return jsonify({

                "success": False,

                "message":
                    "Unable to retrieve file content."

            })

        source_files = []

        for saved_path in saved_files:

            saved_content = get_file_content(

                repository["owner"],
                repository["repo"],
                saved_path,
                repository["default_branch"]

            )

            if saved_content is not None:

                source_files.append({

                    "path": saved_path,

                    "content": saved_content

                })

        # -------------------------------------------------
        # AI
        # -------------------------------------------------

        result = analyze_single_file(

            repository=repository,

            file_path=file_path,

            content=content,

            all_files=source_files

        )

        return jsonify({

            "success": True,

            "analysis": result

        })

    except Exception as error:

        print(
            "SINGLE FILE ANALYSIS ERROR:",
            repr(error)
        )

        return jsonify({

            "success": False,

            "message":
                "Gitora AI could not analyze this file. "
                "Make sure Ollama is running."

        })

    finally:

        db.session.remove()


# =====================================================
# ASK GITORA AI
# =====================================================

@main.route(
    "/ask-ai",
    methods=["POST"]
)
def ask_ai():

    try:

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

                "answer":
                    "Repository information is missing."

            })

        if not question:

            return jsonify({

                "success": False,

                "answer":
                    "Please enter a question."

            })

        # -------------------------------------------------
        # DATABASE
        # -------------------------------------------------

        saved_files = get_saved_file_paths(
            repository_name
        )

        if not saved_files:

            return jsonify({

                "success": False,

                "answer":
                    "Please select and save at least "
                    "one repository file first."

            })

        # -------------------------------------------------
        # GITHUB
        # -------------------------------------------------

        repository = get_repository_info(

            "https://github.com/"
            + repository_name

        )

        source_files = []

        for file_path in saved_files:

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

        if not source_files:

            return jsonify({

                "success": False,

                "answer":
                    "Unable to load the selected files."

            })

        # -------------------------------------------------
        # AI
        # -------------------------------------------------

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
            "AI QUESTION ERROR:",
            repr(error)
        )

        return jsonify({

            "success": False,

            "answer":
                "Gitora AI could not process the "
                "question. Make sure Ollama is running."

        })

    finally:

        db.session.remove()


# =====================================================
# DOWNLOAD COMPLETE PDF REPORT
# =====================================================

@main.route(
    "/download-report",
    methods=["POST"]
)
def download_report():

    print("\n")
    print("=====================================================")
    print("GITORA PDF REPORT REQUEST")
    print("=====================================================")

    try:

        # -------------------------------------------------
        # GET REPOSITORY
        # -------------------------------------------------

        repository_name = request.form.get(
            "repository",
            ""
        ).strip()

        print(
            "Repository:",
            repository_name
        )

        if not repository_name:

            print(
                "PDF ERROR: Repository information missing."
            )

            return (
                "Repository information is missing.",
                400
            )

        # -------------------------------------------------
        # GET SAVED FILES
        # -------------------------------------------------
        #
        # IMPORTANT:
        # This helper reads the DB and immediately releases
        # the connection.
        #
        # Therefore the DB connection is NOT held while
        # GitHub / Ollama / PDF generation happens.
        #
        # -------------------------------------------------

        saved_files = get_saved_file_paths(
            repository_name
        )

        print(
            "Saved files:",
            saved_files
        )

        if not saved_files:

            print(
                "PDF ERROR: No saved files."
            )

            return (
                "Please select and save at least "
                "one file before generating the report.",
                400
            )

        # -------------------------------------------------
        # GET REPOSITORY INFORMATION
        # -------------------------------------------------

        repository = get_repository_info(

            "https://github.com/"
            + repository_name

        )

        print(
            "Repository loaded:",
            repository.get("full_name")
        )

        # -------------------------------------------------
        # LOAD SOURCE FILES
        # -------------------------------------------------

        source_files = []

        for file_path in saved_files:

            print(
                "Loading file:",
                file_path
            )

            content = get_file_content(

                repository["owner"],
                repository["repo"],
                file_path,
                repository["default_branch"]

            )

            if content is not None:

                source_files.append({

                    "path": file_path,

                    "content": content,

                    "categories": categorize_file(
                        file_path
                    )

                })

            else:

                print(
                    "WARNING: Could not load:",
                    file_path
                )

        print(
            "Successfully loaded:",
            len(source_files),
            "files"
        )

        if not source_files:

            return (
                "Unable to load the selected files.",
                400
            )

        # -------------------------------------------------
        # AI ANALYSIS
        # -------------------------------------------------
        #
        # NO DATABASE OPERATION HERE.
        #
        # This is important because Ollama can take a long
        # time and must not hold a DB connection.
        #
        # -------------------------------------------------

        print(
            "Starting Gitora AI analysis for PDF..."
        )

        ai_analysis = analyze_repository(

            repository=repository,

            files=source_files

        )

        if not isinstance(
            ai_analysis,
            dict
        ):

            print(
                "WARNING: AI analysis was not a dictionary."
            )

            ai_analysis = {

                "project_summary":
                    "AI analysis was unavailable.",

                "technology_stack": [],

                "architecture":
                    "AI analysis was unavailable.",

                "dependencies": [],

                "database":
                    "AI analysis was unavailable.",

                "authentication":
                    "AI analysis was unavailable.",

                "important_requests": [],

                "file_analysis": [],

                "rebuild_options": []

            }

        print(
            "AI analysis completed."
        )

        # -------------------------------------------------
        # GENERATE PDF
        # -------------------------------------------------

        print(
            "Generating PDF..."
        )

        pdf_buffer = generate_repository_pdf(

            repository=repository,

            source_files=source_files,

            ai_analysis=ai_analysis

        )

        if pdf_buffer is None:

            raise RuntimeError(
                "PDF service returned no data."
            )

        print(
            "PDF generated successfully."
        )

        # -------------------------------------------------
        # RESET BUFFER POSITION
        # -------------------------------------------------

        try:

            pdf_buffer.seek(0)

        except Exception:

            pass

        # -------------------------------------------------
        # FILE NAME
        # -------------------------------------------------

        filename = (
            repository.get(
                "repo",
                "repository"
            )
            + "_Gitora_Report.pdf"
        )

        print(
            "Sending file:",
            filename
        )

        print(
            "====================================================="
        )

        print(
            "GITORA PDF REPORT SUCCESS"
        )

        print(
            "====================================================="
        )

        return send_file(

            pdf_buffer,

            mimetype="application/pdf",

            as_attachment=True,

            download_name=filename

        )

    except Exception as error:

        print(
            "\n====================================================="
        )

        print(
            "GITORA PDF GENERATION FAILED"
        )

        print(
            "ERROR TYPE:",
            type(error).__name__
        )

        print(
            "ERROR:",
            repr(error)
        )

        print(
            "=====================================================\n"
        )

        return (
            "Unable to generate the PDF report. "
            "Check the Flask terminal for the exact error.",
            500
        )

    finally:

        # -------------------------------------------------
        # FINAL DATABASE CLEANUP
        # -------------------------------------------------

        try:

            db.session.remove()

        except Exception as error:

            print(
                "FINAL DATABASE CLEANUP ERROR:",
                repr(error)
            )