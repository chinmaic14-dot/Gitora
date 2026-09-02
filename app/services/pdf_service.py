# app/services/pdf_service.py

from io import BytesIO
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Preformatted
)


# =====================================================
# SAFE HELPERS
# =====================================================

def safe_text(value, default="Not available."):

    if value is None:
        return default

    if isinstance(value, bool):
        return "Yes" if value else "No"

    if isinstance(value, (dict, list, tuple, set)):

        if isinstance(value, dict):

            parts = []

            for key, val in value.items():

                parts.append(
                    f"{key}: {safe_text(val, '')}"
                )

            return "\n".join(parts)

        parts = []

        for item in value:

            text = safe_text(
                item,
                ""
            )

            if text:
                parts.append(text)

        return "\n".join(parts)

    try:

        text = str(value).strip()

        return text if text else default

    except Exception:

        return default


def safe_list(value):

    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, set):
        return list(value)

    if isinstance(value, dict):

        return [
            f"{key}: {safe_text(val, '')}"
            for key, val in value.items()
        ]

    if isinstance(value, str):

        text = value.strip()

        if not text:
            return []

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        return lines if lines else [text]

    return [value]


def escape_html(value):

    return escape(
        safe_text(value)
    ).replace(
        "\n",
        "<br/>"
    )


# =====================================================
# PAGE HEADER / FOOTER
# =====================================================

def draw_page(canvas, document):

    canvas.saveState()

    width, height = A4

    # -------------------------------------------------
    # Dark page border
    # -------------------------------------------------

    canvas.setStrokeColor(
        colors.HexColor("#202040")
    )

    canvas.setLineWidth(1)

    canvas.rect(
        8 * mm,
        8 * mm,
        width - 16 * mm,
        height - 16 * mm
    )

    # -------------------------------------------------
    # Footer
    # -------------------------------------------------

    canvas.setFont(
        "Helvetica",
        8
    )

    canvas.setFillColor(
        colors.HexColor("#666666")
    )

    canvas.drawCentredString(
        width / 2,
        12 * mm,
        f"Gitora AI • Page {document.page}"
    )

    canvas.restoreState()


# =====================================================
# STYLES
# =====================================================

def create_styles():

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="GitoraTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=27,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#1A1A2E"),
            spaceAfter=12
        )
    )

    styles.add(
        ParagraphStyle(
            name="GitoraSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#666666"),
            spaceAfter=18
        )
    )

    styles.add(
        ParagraphStyle(
            name="GitoraSection",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=19,
            textColor=colors.HexColor("#1A1A2E"),
            spaceBefore=12,
            spaceAfter=9
        )
    )

    styles.add(
        ParagraphStyle(
            name="GitoraSubsection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#303050"),
            spaceBefore=7,
            spaceAfter=5
        )
    )

    styles.add(
        ParagraphStyle(
            name="GitoraBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#303030"),
            spaceAfter=6
        )
    )

    styles.add(
        ParagraphStyle(
            name="GitoraBullet",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            leftIndent=12,
            firstLineIndent=-7,
            textColor=colors.HexColor("#303030"),
            spaceAfter=4
        )
    )

    styles.add(
        ParagraphStyle(
            name="GitoraCode",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=6.5,
            leading=8,
            textColor=colors.HexColor("#202020"),
            backColor=colors.HexColor("#F5F5F5"),
            borderPadding=5
        )
    )

    styles.add(
        ParagraphStyle(
            name="GitoraSmall",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#555555")
        )
    )

    return styles


# =====================================================
# SECTION TITLE
# =====================================================

def section_title(title, styles):

    return [
        Spacer(1, 5 * mm),
        Paragraph(
            escape_html(title),
            styles["GitoraSection"]
        )
    ]


# =====================================================
# BULLET LIST
# =====================================================

def bullet_list(items, styles):

    story = []

    items = safe_list(items)

    if not items:

        story.append(
            Paragraph(
                "Not available.",
                styles["GitoraBody"]
            )
        )

        return story

    for item in items:

        text = safe_text(
            item,
            "Not available."
        )

        story.append(
            Paragraph(
                "• " + escape_html(text),
                styles["GitoraBullet"]
            )
        )

    return story


# =====================================================
# ANALYSIS BOX
# =====================================================

def create_analysis_box(
    title,
    content,
    styles
):

    content = safe_text(
        content,
        "Not available."
    )

    table_data = [
        [
            Paragraph(
                escape_html(title),
                styles["GitoraSubsection"]
            )
        ],
        [
            Paragraph(
                escape_html(content),
                styles["GitoraBody"]
            )
        ]
    ]

    table = Table(
        table_data,
        colWidths=[170 * mm]
    )

    table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#EEEEF8")
            ),
            (
                "BACKGROUND",
                (0, 1),
                (-1, 1),
                colors.HexColor("#FAFAFC")
            ),
            (
                "BOX",
                (0, 0),
                (-1, -1),
                0.7,
                colors.HexColor("#CCCCDD")
            ),
            (
                "INNERGRID",
                (0, 0),
                (-1, -1),
                0.3,
                colors.HexColor("#DDDDDD")
            ),
            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                8
            ),
            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                8
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                6
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                6
            )
        ])
    )

    return table


# =====================================================
# FILE-BY-FILE ANALYSIS
# =====================================================

def build_file_analysis(
    file_analysis,
    styles
):

    story = []

    if not isinstance(
        file_analysis,
        list
    ):

        file_analysis = []

    if not file_analysis:

        story.append(
            Paragraph(
                "AI file-by-file analysis is not available.",
                styles["GitoraBody"]
            )
        )

        return story

    for item in file_analysis:

        if not isinstance(
            item,
            dict
        ):

            continue

        file_name = (
            item.get("file")
            or item.get("path")
            or item.get("filename")
            or "Unknown file"
        )

        what_it_does = (
            item.get("what_it_does")
            or item.get("description")
            or item.get("purpose")
            or item.get("function")
        )

        why_it_exists = (
            item.get("why_it_exists")
            or item.get("why")
            or item.get("reason")
        )

        website_role = (
            item.get("website_role")
            or item.get("how_it_helps")
            or item.get("role")
            or item.get("connections")
        )

        dependencies = (
            item.get("dependencies")
            or item.get("required_files")
            or item.get("imports")
            or []
        )

        requests = (
            item.get("important_requests")
            or item.get("api_requests")
            or item.get("requests")
            or []
        )

        what_breaks = (
            item.get("what_breaks")
            or item.get("what_breaks_without_it")
            or item.get("impact")
            or item.get("consequence")
        )

        story.append(
            Paragraph(
                escape_html(file_name),
                styles["GitoraSubsection"]
            )
        )

        story.append(
            create_analysis_box(
                "What it does",
                what_it_does,
                styles
            )
        )

        story.append(
            Spacer(1, 3 * mm)
        )

        story.append(
            create_analysis_box(
                "Why it exists",
                why_it_exists,
                styles
            )
        )

        story.append(
            Spacer(1, 3 * mm)
        )

        story.append(
            create_analysis_box(
                "How it helps the website / project",
                website_role,
                styles
            )
        )

        story.append(
            Spacer(1, 3 * mm)
        )

        story.append(
            Paragraph(
                "Dependencies",
                styles["GitoraSubsection"]
            )
        )

        story.extend(
            bullet_list(
                dependencies,
                styles
            )
        )

        story.append(
            Paragraph(
                "Important API Requests",
                styles["GitoraSubsection"]
            )
        )

        story.extend(
            bullet_list(
                requests,
                styles
            )
        )

        story.append(
            create_analysis_box(
                "What breaks without it",
                what_breaks,
                styles
            )
        )

        story.append(
            Spacer(1, 5 * mm)
        )

    return story


# =====================================================
# API REQUESTS
# =====================================================

def build_api_requests(
    requests,
    styles
):

    story = []

    requests = safe_list(
        requests
    )

    if not requests:

        story.append(
            Paragraph(
                "No important API requests were identified.",
                styles["GitoraBody"]
            )
        )

        return story

    for request_item in requests:

        if isinstance(
            request_item,
            dict
        ):

            method = (
                request_item.get("method")
                or request_item.get("http_method")
                or ""
            )

            endpoint = (
                request_item.get("endpoint")
                or request_item.get("url")
                or request_item.get("path")
                or ""
            )

            description = (
                request_item.get("description")
                or request_item.get("purpose")
                or ""
            )

            text_parts = []

            if method:
                text_parts.append(
                    f"{method}"
                )

            if endpoint:
                text_parts.append(
                    endpoint
                )

            if description:
                text_parts.append(
                    description
                )

            text = " — ".join(
                text_parts
            )

        else:

            text = safe_text(
                request_item
            )

        story.append(
            Paragraph(
                "• " + escape_html(text),
                styles["GitoraBullet"]
            )
        )

    return story


# =====================================================
# REBUILD OPTIONS
# =====================================================

def build_rebuild_options(
    options,
    styles
):

    story = []

    options = safe_list(
        options
    )

    if not options:

        story.append(
            Paragraph(
                "No rebuild strategies were generated.",
                styles["GitoraBody"]
            )
        )

        return story

    for index, option in enumerate(
        options[:3],
        start=1
    ):

        if isinstance(
            option,
            dict
        ):

            title = (
                option.get("title")
                or option.get("name")
                or f"Approach {index}"
            )

            description = (
                option.get("description")
                or option.get("details")
                or option.get("approach")
                or ""
            )

            technology = (
                option.get("technology")
                or option.get("stack")
                or ""
            )

            time = (
                option.get("estimated_time")
                or option.get("time")
                or ""
            )

            content_parts = []

            if description:
                content_parts.append(
                    description
                )

            if technology:
                content_parts.append(
                    f"Technology: {technology}"
                )

            if time:
                content_parts.append(
                    f"Estimated time: {time}"
                )

            content = "\n".join(
                content_parts
            )

        else:

            title = f"Approach {index}"

            content = safe_text(
                option
            )

        story.append(
            Paragraph(
                escape_html(
                    f"{index}. {title}"
                ),
                styles["GitoraSubsection"]
            )
        )

        story.append(
            Paragraph(
                escape_html(content),
                styles["GitoraBody"]
            )
        )

    return story


# =====================================================
# SOURCE CODE
# =====================================================

def build_source_code(
    source_files,
    styles
):

    story = []

    if not isinstance(
        source_files,
        list
    ):

        source_files = []

    if not source_files:

        story.append(
            Paragraph(
                "No source files were selected.",
                styles["GitoraBody"]
            )
        )

        return story

    for file_item in source_files:

        if not isinstance(
            file_item,
            dict
        ):

            continue

        file_path = (
            file_item.get("path")
            or file_item.get("file")
            or "Unknown file"
        )

        content = (
            file_item.get("content")
            or ""
        )

        content = safe_text(
            content,
            ""
        )

        if len(content) > 120000:

            content = (
                content[:120000]
                + "\n\n"
                + "[Source code truncated for PDF size safety.]"
            )

        story.append(
            Paragraph(
                escape_html(file_path),
                styles["GitoraSubsection"]
            )
        )

        if not content:

            story.append(
                Paragraph(
                    "No source code available.",
                    styles["GitoraBody"]
                )
            )

        else:

            # Preformatted is much safer than putting source
            # code inside Paragraph HTML.

            story.append(
                Preformatted(
                    content,
                    styles["GitoraCode"],
                    maxLineLength=110
                )
            )

        story.append(
            Spacer(1, 5 * mm)
        )

    return story


# =====================================================
# MAIN PDF GENERATOR
# =====================================================

def generate_repository_pdf(
    repository,
    source_files,
    ai_analysis
):

    print("\n========================================")
    print("🔥 PDF SERVICE STARTED")
    print("========================================")

    try:

        # -------------------------------------------------
        # Validate inputs
        # -------------------------------------------------

        if not isinstance(
            repository,
            dict
        ):

            repository = {}

        if not isinstance(
            source_files,
            list
        ):

            source_files = []

        if not isinstance(
            ai_analysis,
            dict
        ):

            ai_analysis = {}

        print(
            "Repository:",
            repository.get(
                "full_name",
                repository.get(
                    "repo",
                    "Unknown"
                )
            )
        )

        print(
            "Source files:",
            len(source_files)
        )

        print(
            "AI analysis type:",
            type(ai_analysis).__name__
        )

        # -------------------------------------------------
        # Create PDF buffer
        # -------------------------------------------------

        pdf_buffer = BytesIO()

        document = SimpleDocTemplate(
            pdf_buffer,
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
            title="Gitora Repository Analysis Report",
            author="Gitora AI"
        )

        styles = create_styles()

        story = []

        # =================================================
        # REPOSITORY INFORMATION
        # =================================================

        repo_name = (
            repository.get("full_name")
            or repository.get("name")
            or repository.get("repo")
            or "GitHub Repository"
        )

        repo_url = (
            repository.get("html_url")
            or repository.get("url")
            or ""
        )

        description = (
            repository.get("description")
            or "GitHub repository analyzed by Gitora AI."
        )

        # =================================================
        # COVER
        # =================================================

        story.append(
            Spacer(1, 25 * mm)
        )

        story.append(
            Paragraph(
                "GITORA AI",
                styles["GitoraTitle"]
            )
        )

        story.append(
            Paragraph(
                "Repository Analysis Report",
                styles["GitoraSubtitle"]
            )
        )

        story.append(
            create_analysis_box(
                "Repository",
                repo_name,
                styles
            )
        )

        story.append(
            Spacer(1, 5 * mm)
        )

        story.append(
            create_analysis_box(
                "Description",
                description,
                styles
            )
        )

        if repo_url:

            story.append(
                Spacer(1, 4 * mm)
            )

            story.append(
                Paragraph(
                    escape_html(repo_url),
                    styles["GitoraSmall"]
                )
            )

        story.append(
            Spacer(1, 12 * mm)
        )

        story.append(
            Paragraph(
                "Generated by Gitora",
                styles["GitoraSubtitle"]
            )
        )

        story.append(
            PageBreak()
        )

        # =================================================
        # AI DATA
        # =================================================

        project_summary = (
            ai_analysis.get("project_summary")
            or ai_analysis.get("summary")
            or ai_analysis.get("projectSummary")
        )

        technology_stack = (
            ai_analysis.get("technology_stack")
            or ai_analysis.get("tech_stack")
            or ai_analysis.get("technologyStack")
            or []
        )

        architecture = (
            ai_analysis.get("architecture")
            or ai_analysis.get("system_architecture")
        )

        dependencies = (
            ai_analysis.get("dependencies")
            or []
        )

        database = (
            ai_analysis.get("database")
            or ai_analysis.get("database_structure")
        )

        authentication = (
            ai_analysis.get("authentication")
            or ai_analysis.get("auth")
        )

        important_requests = (
            ai_analysis.get("important_requests")
            or ai_analysis.get("api_requests")
            or ai_analysis.get("importantRequests")
            or []
        )

        rebuild_options = (
            ai_analysis.get("rebuild_options")
            or ai_analysis.get("rebuildWays")
            or []
        )

        file_analysis = (
            ai_analysis.get("file_analysis")
            or ai_analysis.get("files_analysis")
            or ai_analysis.get("fileAnalysis")
            or []
        )

        estimated_time = (
            ai_analysis.get(
                "estimated_development_time"
            )
            or ai_analysis.get(
                "estimated_time"
            )
            or ai_analysis.get(
                "development_time"
            )
        )

        routing = (
            ai_analysis.get(
                "routing"
            )
            or ai_analysis.get(
                "routes"
            )
            or []
        )

        run_instructions = (
            ai_analysis.get(
                "run_instructions"
            )
            or ai_analysis.get(
                "runInstructions"
            )
            or []
        )

        folder_structure = (
            ai_analysis.get(
                "folder_structure"
            )
            or ai_analysis.get(
                "folderStructure"
            )
        )

        # =================================================
        # 1. PROJECT UNDERSTANDING
        # =================================================

        story.extend(
            section_title(
                "1. Project Understanding",
                styles
            )
        )

        story.append(
            create_analysis_box(
                "What this project does",
                project_summary,
                styles
            )
        )

        if estimated_time:

            story.append(
                Spacer(1, 4 * mm)
            )

            story.append(
                create_analysis_box(
                    "Estimated Development Time",
                    estimated_time,
                    styles
                )
            )

        # =================================================
        # 2. TECHNOLOGY STACK
        # =================================================

        story.extend(
            section_title(
                "2. Technology Stack",
                styles
            )
        )

        story.extend(
            bullet_list(
                technology_stack,
                styles
            )
        )

        # =================================================
        # 3. ARCHITECTURE
        # =================================================

        story.extend(
            section_title(
                "3. Architecture",
                styles
            )
        )

        story.append(
            create_analysis_box(
                "System Architecture",
                architecture,
                styles
            )
        )

        if folder_structure:

            story.append(
                Spacer(1, 4 * mm)
            )

            story.append(
                create_analysis_box(
                    "Folder Structure",
                    folder_structure,
                    styles
                )
            )

        if routing:

            story.append(
                Paragraph(
                    "Routing",
                    styles["GitoraSubsection"]
                )
            )

            story.extend(
                bullet_list(
                    routing,
                    styles
                )
            )

        # =================================================
        # 4. DEPENDENCIES
        # =================================================

        story.extend(
            section_title(
                "4. Dependencies",
                styles
            )
        )

        story.extend(
            bullet_list(
                dependencies,
                styles
            )
        )

        # =================================================
        # 5. DATABASE
        # =================================================

        story.extend(
            section_title(
                "5. Database",
                styles
            )
        )

        story.append(
            create_analysis_box(
                "Database Structure",
                database,
                styles
            )
        )

        # =================================================
        # 6. AUTHENTICATION
        # =================================================

        story.extend(
            section_title(
                "6. Authentication",
                styles
            )
        )

        story.append(
            create_analysis_box(
                "Authentication / Login",
                authentication,
                styles
            )
        )

        # =================================================
        # 7. API REQUESTS
        # =================================================

        story.extend(
            section_title(
                "7. Important API Requests",
                styles
            )
        )

        story.extend(
            build_api_requests(
                important_requests,
                styles
            )
        )

        # =================================================
        # 8. REBUILD OPTIONS
        # =================================================

        story.extend(
            section_title(
                "8. Three Ways to Rebuild This Project",
                styles
            )
        )

        story.extend(
            build_rebuild_options(
                rebuild_options,
                styles
            )
        )

        # =================================================
        # 9. FILE-BY-FILE EXPLANATION
        # =================================================

        story.extend(
            section_title(
                "9. File-by-File Explanation",
                styles
            )
        )

        story.extend(
            build_file_analysis(
                file_analysis,
                styles
            )
        )

        # =================================================
        # 10. SELECTED SOURCE FILES
        # =================================================

        story.extend(
            section_title(
                "10. Selected Source Files",
                styles
            )
        )

        for file_item in source_files:

            if not isinstance(
                file_item,
                dict
            ):

                continue

            path = (
                file_item.get("path")
                or "Unknown file"
            )

            categories = file_item.get(
                "categories",
                []
            )

            category_text = ", ".join(
                safe_text(item, "")
                for item in safe_list(
                    categories
                )
            )

            if category_text:

                text = (
                    f"{path} — {category_text}"
                )

            else:

                text = path

            story.append(
                Paragraph(
                    "• " + escape_html(text),
                    styles["GitoraBullet"]
                )
            )

        # =================================================
        # 11. COMPLETE SELECTED SOURCE CODE
        # =================================================

        story.extend(
            section_title(
                "11. Complete Selected Source Code",
                styles
            )
        )

        story.extend(
            build_source_code(
                source_files,
                styles
            )
        )

        # =================================================
        # BUILD DOCUMENT
        # =================================================

        print(
            "Building ReportLab document..."
        )

        document.build(
            story,
            onFirstPage=draw_page,
            onLaterPages=draw_page
        )

        # =================================================
        # VALIDATE PDF
        # =================================================

        pdf_buffer.seek(0)

        pdf_data = pdf_buffer.getvalue()

        pdf_size = len(
            pdf_data
        )

        print(
            "Generated PDF size:",
            pdf_size,
            "bytes"
        )

        if pdf_size == 0:

            raise RuntimeError(
                "Generated PDF is empty."
            )

        if not pdf_data.startswith(
            b"%PDF"
        ):

            raise RuntimeError(
                "Generated data is not a valid PDF."
            )

        pdf_buffer.seek(0)

        print(
            "========================================"
        )

        print(
            "✅ PDF SERVICE COMPLETED"
        )

        print(
            "========================================"
        )

        return pdf_buffer

    except Exception as error:

        print(
            "\n========================================"
        )

        print(
            "❌ PDF SERVICE ERROR"
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

        raise