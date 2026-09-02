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
# DATABASE SESSION CLEANUP
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
# HELPER
# =====================================================

def get_saved_file_paths(repository_name):

    try:

        records = (
            SavedFileSelection.query
            .filter_by(repository=repository_name)
            .all()
        )

        return [
            record.file_path
            for record in records
        ]

    finally:

        db.session.remove()


# =====================================================
# HOME
# =====================================================

@main.route("/")
def home():

    return render_template("index.html")


# =====================================================
# ANALYZE REPOSITORY
# =====================================================

@main.route("/analyze", methods=["POST"])
def analyze():

    print("\n========================================")
    print("🔥 GITORA ANALYZE ROUTE REACHED")
    print("========================================")

    repo_url = request.form.get(
        "repo_url",
        ""
    ).strip()

    print("Repository URL:", repo_url)

    if not repo_url:

        print("ERROR: Repository URL is empty.")

        return render_template(
            "index.html",
            error="Please enter a GitHub repository URL."
        )

    try:

        print("Getting repository information...")

        repository = get_repository_info(
            repo_url
        )

        print(
            "Repository loaded:",
            repository.get("full_name")
        )

        print("Getting repository files...")

        files = get_repository_files(
            repository["owner"],
            repository["repo"],
            repository["default_branch"]
        )

        print(
            "Files received:",
            len(files)
        )

        categorized_files = []

        for file in files:

            categorized_files.append({
                "path": file["path"],
                "categories": categorize_file(
                    file["path"]
                )
            })

        saved_files = get_saved_file_paths(
            repository["full_name"]
        )

        print(
            "Saved files:",
            saved_files
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

        print("Opening analysis.html...")

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

        print(
            "ANALYZE VALUE ERROR:",
            repr(error)
        )

        return render_template(
            "index.html",
            error=str(error)
        )

    except Exception as error:

        print("\n========================================")
        print("❌ ANALYZE REPOSITORY FAILED")
        print("ERROR TYPE:", type(error).__name__)
        print("ERROR:", repr(error))
        print("========================================")

        return render_template(
            "index.html",
            error=(
                "Unable to analyze this repository: "
                + str(error)
            )
        )


# =====================================================
# SAVE SELECTED FILES
# =====================================================

@main.route("/save-files", methods=["POST"])
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

        SavedFileSelection.query.filter_by(
            repository=repository
        ).delete(
            synchronize_session=False
        )

        for file_path in selected_files:

            db.session.add(
                SavedFileSelection(
                    repository=repository,
                    file_path=file_path
                )
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

        db.session.remove()

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
# FULL AI ANALYSIS - GEMINI
# =====================================================

@main.route("/ai-analyze", methods=["POST"])
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

        print(
            "Starting Gemini analysis..."
        )

        result = analyze_repository(
            repository=repository,
            files=source_files
        )

        if not isinstance(result, dict):

            return jsonify({
                "success": False,
                "message":
                    "Gitora AI returned an invalid response."
            })

        rebuild_ways = result.get(
            "rebuild_ways",
            result.get("rebuild_options", [])
        )

        return jsonify({
            "success": True,
            "analysis": result,
            "rebuild_options": rebuild_ways
        })

    except Exception as error:

        print(
            "AI ANALYSIS ERROR:",
            type(error).__name__,
            repr(error)
        )

        return jsonify({
            "success": False,
            "message":
                "Gitora AI could not analyze the repository. "
                "Check your GEMINI_API_KEY configuration."
        })

    finally:

        db.session.remove()


# =====================================================
# THREE WAYS TO REBUILD
# =====================================================

@main.route("/rebuild-options", methods=["POST"])
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

        analysis = analyze_repository(
            repository=repository,
            files=source_files
        )

        if not isinstance(analysis, dict):

            return jsonify({
                "success": False,
                "message":
                    "Gitora AI returned an invalid analysis."
            })

        options = analysis.get(
            "rebuild_ways",
            analysis.get("rebuild_options", [])
        )

        if not isinstance(options, list):

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
            type(error).__name__,
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
# ANALYZE ONE FILE - GEMINI
# =====================================================

@main.route("/analyze-file", methods=["POST"])
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

        saved_files = get_saved_file_paths(
            repository_name
        )

        if file_path not in saved_files:

            return jsonify({
                "success": False,
                "message":
                    "This file has not been saved."
            })

        repository = get_repository_info(
            "https://github.com/"
            + repository_name
        )

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

        if not source_files:

            return jsonify({
                "success": False,
                "message":
                    "Unable to load the selected files."
            })

        result = analyze_single_file(
            repository=repository,
            files=source_files,
            selected_file=file_path
        )

        return jsonify({
            "success": True,
            "analysis": result
        })

    except Exception as error:

        print(
            "SINGLE FILE ANALYSIS ERROR:",
            type(error).__name__,
            repr(error)
        )

        return jsonify({
            "success": False,
            "message":
                "Gitora AI could not analyze this file. "
                "Check your GEMINI_API_KEY configuration."
        })

    finally:

        db.session.remove()


# =====================================================
# ASK GITORA AI - GEMINI
# =====================================================

@main.route("/ask-ai", methods=["POST"])
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
            type(error).__name__,
            repr(error)
        )

        return jsonify({
            "success": False,
            "answer":
                "Gitora AI could not process the question. "
                "Check your GEMINI_API_KEY configuration."
        })

    finally:

        db.session.remove()


# =====================================================
# DOWNLOAD COMPLETE PDF REPORT
# =====================================================

@main.route("/download-report", methods=["POST"])
def download_report():

    print("\n========================================")
    print("GITORA PDF REPORT REQUEST")
    print("========================================")

    try:

        repository_name = request.form.get(
            "repository",
            ""
        ).strip()

        print(
            "Repository:",
            repository_name
        )

        if not repository_name:

            return (
                "Repository information is missing.",
                400
            )

        saved_files = get_saved_file_paths(
            repository_name
        )

        print(
            "Saved files:",
            saved_files
        )

        if not saved_files:

            return (
                "Please select and save at least "
                "one file before generating the report.",
                400
            )

        repository = get_repository_info(
            "https://github.com/"
            + repository_name
        )

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

        if not source_files:

            return (
                "Unable to load the selected files.",
                400
            )

        print(
            "Starting Gitora Gemini analysis for PDF..."
        )

        ai_analysis = analyze_repository(
            repository=repository,
            files=source_files
        )

        if not isinstance(ai_analysis, dict):

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
                "rebuild_ways": []
            }

        print(
            "AI analysis completed."
        )

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

        try:

            pdf_buffer.seek(0)

        except Exception:

            pass

        filename = (
            repository.get(
                "repo",
                "repository"
            )
            + "_Gitora_Report.pdf"
        )

        print(
            "PDF generated successfully."
        )

        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )

    except Exception as error:

        print(
            "========================================"
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
            "========================================"
        )

        return (
            "Unable to generate the PDF report. "
            "Check the Flask terminal for the exact error.",
            500
        )

    finally:

        try:

            db.session.remove()

        except Exception as error:

            print(
                "FINAL DATABASE CLEANUP ERROR:",
                repr(error)
            )