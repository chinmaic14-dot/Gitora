import json
import re
import os

from google import genai


# ============================================================
# GEMINI CONFIGURATION
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash"
)

client = None

if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print("\n========== GITORA GEMINI CLIENT ERROR ==========")
        print(repr(e))
        print("=================================================\n")
        client = None


NIL = "None identified."


# ============================================================
# BASIC HELPERS
# ============================================================

def safe_value(value, default=NIL):

    if value is None:
        return default

    if isinstance(value, str):

        value = value.strip()

        if not value:
            return default

        return value

    return value


def normalize_list(value):

    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, str):

        value = value.strip()

        if not value:
            return []

        return [value]

    return [value]


# ============================================================
# REPOSITORY CONTEXT
# ============================================================

def build_repository_context(repository, files):

    repository = repository or {}

    parts = []

    parts.append(
        "GITORA REPOSITORY ANALYSIS\n"
    )

    parts.append(
        f"Repository: "
        f"{repository.get('full_name', 'Unknown')}"
    )

    parts.append(
        f"Description: "
        f"{repository.get('description', NIL)}"
    )

    parts.append(
        f"Default branch: "
        f"{repository.get('default_branch', NIL)}"
    )

    parts.append(
        f"Language: "
        f"{repository.get('language', NIL)}"
    )

    parts.append(
        "\nIMPORTANT RULES:\n"
        "- Analyze ONLY the supplied repository information and source code.\n"
        "- Do not invent frameworks.\n"
        "- Do not invent APIs.\n"
        "- Do not invent databases.\n"
        "- Do not invent authentication systems.\n"
        "- Do not invent files that were not supplied.\n"
        "- If something cannot be determined, say 'None identified.'\n"
    )

    parts.append("\nSOURCE FILES:\n")

    for file_item in files or []:

        if isinstance(file_item, dict):

            path = (
                file_item.get("path")
                or file_item.get("name")
                or "unknown"
            )

            content = (
                file_item.get("content")
                or ""
            )

        else:

            path = str(file_item)
            content = ""

        # Prevent extremely large prompts.
        content = content[:30000]

        parts.append(
            f"\n========== FILE: {path} ==========\n"
        )

        parts.append(content)

        parts.append(
            f"\n========== END FILE: {path} ==========\n"
        )

    return "\n".join(parts)


# ============================================================
# EMPTY RESPONSES
# ============================================================

def empty_analysis(message=NIL):

    return {

        "project_summary": message,

        "technology_stack": [],

        "architecture": message,

        "dependencies": [],

        "database": message,

        "authentication": message,

        "important_requests": [],

        "file_analysis": [],

        "project_flow": [],

        "important_files": [],

        "failure_points": [],

        "build_approaches": [],

        "rebuild_ways": [],

        "rebuild_options": [],

        "estimated_development_time": message,

        "run_instructions": [],

        "folder_structure": message
    }


def empty_file_analysis(message=NIL):

    return {

        "file": "",

        "what_it_does": message,

        "why_it_exists": message,

        "what_breaks_without_it": message,

        "important_code": [],

        "dependencies": [],

        "connections": []
    }


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(text):

    if not text:
        return None

    text = text.strip()

    # Remove markdown code fences.
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    text = text.strip()

    try:
        return json.loads(text)

    except Exception:
        pass

    # Try to locate the first JSON object.
    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1 and end > start:

        candidate = text[start:end + 1]

        try:
            return json.loads(candidate)

        except Exception:
            pass

    return None


# ============================================================
# NORMALIZE REPOSITORY ANALYSIS
# ============================================================

def normalize_analysis(result):

    if not isinstance(result, dict):

        return empty_analysis(
            "Gemini returned an invalid analysis response."
        )

    result["project_summary"] = safe_value(
        result.get("project_summary")
    )

    result["technology_stack"] = normalize_list(
        result.get("technology_stack")
    )

    result["architecture"] = safe_value(
        result.get("architecture")
    )

    result["dependencies"] = normalize_list(
        result.get("dependencies")
    )

    result["database"] = safe_value(
        result.get("database")
    )

    result["authentication"] = safe_value(
        result.get("authentication")
    )

    result["important_requests"] = normalize_list(
        result.get("important_requests")
    )

    result["file_analysis"] = normalize_list(
        result.get("file_analysis")
    )

    result["project_flow"] = normalize_list(
        result.get("project_flow")
    )

    result["important_files"] = normalize_list(
        result.get("important_files")
    )

    result["failure_points"] = normalize_list(
        result.get("failure_points")
    )

    # --------------------------------------------------------
    # Rebuild ways
    # --------------------------------------------------------

    rebuild_ways = result.get("rebuild_ways")

    if not rebuild_ways:

        rebuild_ways = result.get(
            "rebuild_options"
        )

    if not rebuild_ways:

        rebuild_ways = result.get(
            "build_approaches"
        )

    rebuild_ways = normalize_list(
        rebuild_ways
    )

    result["rebuild_ways"] = rebuild_ways[:3]

    # Keep all aliases for compatibility with routes/frontend.
    result["rebuild_options"] = result["rebuild_ways"]

    result["build_approaches"] = result["rebuild_ways"]

    result["estimated_development_time"] = safe_value(
        result.get("estimated_development_time")
    )

    result["run_instructions"] = normalize_list(
        result.get("run_instructions")
    )

    result["folder_structure"] = safe_value(
        result.get("folder_structure")
    )

    return result


# ============================================================
# NORMALIZE FILE ANALYSIS
# ============================================================

def normalize_file_analysis(result):

    if not isinstance(result, dict):

        return empty_file_analysis(
            "Gemini returned an invalid file analysis."
        )

    result["file"] = safe_value(
        result.get("file"),
        ""
    )

    result["what_it_does"] = safe_value(
        result.get("what_it_does")
    )

    result["why_it_exists"] = safe_value(
        result.get("why_it_exists")
    )

    result["what_breaks_without_it"] = safe_value(
        result.get("what_breaks_without_it")
    )

    result["important_code"] = normalize_list(
        result.get("important_code")
    )

    result["dependencies"] = normalize_list(
        result.get("dependencies")
    )

    result["connections"] = normalize_list(
        result.get("connections")
    )

    return result


# ============================================================
# GEMINI JSON CALL
# ============================================================

def call_gemini_json(
    system_prompt,
    user_prompt
):

    if client is None:

        print(
            "\n========== GITORA GEMINI ERROR =========="
        )

        print(
            "GEMINI_API_KEY is not configured."
        )

        print(
            "=========================================\n"
        )

        return None

    try:

        prompt = (
            system_prompt
            + "\n\n"
            + user_prompt
        )

        response = client.models.generate_content(

            model=MODEL,

            contents=prompt,

            config={
                "response_mime_type": "application/json"
            }
        )

        raw = response.text

        print(
            "\n========== GITORA GEMINI RESPONSE =========="
        )

        print(raw)

        print(
            "=============================================\n"
        )

        parsed = extract_json(raw)

        if parsed is not None:
            return parsed

        print(
            "\n========== GITORA GEMINI JSON ERROR =========="
        )

        print(
            "Gemini response could not be parsed as JSON."
        )

        print(
            "===============================================\n"
        )

        return None

    except Exception as e:

        print(
            "\n========== GITORA GEMINI ERROR =========="
        )

        print(
            f"Error type: {type(e).__name__}"
        )

        print(
            f"Error: {repr(e)}"
        )

        print(
            "=========================================\n"
        )

        return None


# ============================================================
# FULL REPOSITORY ANALYSIS
# ============================================================

def analyze_repository(
    repository,
    files
):

    if client is None:

        return empty_analysis(
            "Gemini API key is not configured."
        )

    context = build_repository_context(
        repository,
        files
    )

    system_prompt = """
You are Gitora, an expert software repository analyst.

Analyze the supplied GitHub repository source code.

Your analysis MUST be based only on the supplied repository
metadata and source files.

Do not invent technologies, APIs, databases, authentication,
routes, dependencies, files, or functionality.

Return ONLY valid JSON.

The JSON must contain these fields:

{
    "project_summary": "",
    "technology_stack": [],
    "architecture": "",
    "dependencies": [],
    "database": "",
    "authentication": "",
    "important_requests": [],
    "file_analysis": [],
    "project_flow": [],
    "important_files": [],
    "failure_points": [],
    "rebuild_ways": [],
    "estimated_development_time": "",
    "run_instructions": [],
    "folder_structure": ""
}

IMPORTANT:

- file_analysis must analyze every supplied file.
- rebuild_ways must contain exactly 3 practical ways to rebuild
  or improve the project.
- Explain the actual architecture found in the code.
- Identify actual routes/API endpoints when visible.
- Identify actual database models when visible.
- Identify actual authentication when visible.
- Explain what each important file does.
- Mention missing or risky areas only when supported by the code.
"""

    user_prompt = f"""
Analyze this repository:

{context}
"""

    result = call_gemini_json(
        system_prompt,
        user_prompt
    )

    if result is None:

        return empty_analysis(
            "Gemini analysis failed. Check the terminal for the exact error."
        )

    return normalize_analysis(
        result
    )


# ============================================================
# SINGLE FILE ANALYSIS
# ============================================================

def analyze_single_file(
    repository,
    files,
    selected_file
):

    if client is None:

        return empty_file_analysis(
            "Gemini API key is not configured."
        )

    selected_content = ""

    for file_item in files or []:

        if not isinstance(file_item, dict):
            continue

        path = (
            file_item.get("path")
            or file_item.get("name")
            or ""
        )

        if path == selected_file:

            selected_content = (
                file_item.get("content")
                or ""
            )

            break

    if not selected_content:

        return empty_file_analysis(
            f"File '{selected_file}' was not found."
        )

    selected_content = selected_content[:30000]

    system_prompt = """
You are Gitora, an expert software engineer.

Analyze ONE source file from a GitHub repository.

Use only the supplied source code.

Do not invent functionality.

Return ONLY valid JSON with exactly these fields:

{
    "file": "",
    "what_it_does": "",
    "why_it_exists": "",
    "what_breaks_without_it": "",
    "important_code": [],
    "dependencies": [],
    "connections": []
}
"""

    user_prompt = f"""
Repository:
{repository.get('full_name', 'Unknown') if repository else 'Unknown'}

File:
{selected_file}

Source code:

========== SOURCE ==========
{selected_content}
========== END SOURCE ==========
"""

    result = call_gemini_json(
        system_prompt,
        user_prompt
    )

    if result is None:

        return empty_file_analysis(
            "Gemini file analysis failed."
        )

    result = normalize_file_analysis(
        result
    )

    if not result.get("file"):
        result["file"] = selected_file

    return result


# ============================================================
# ASK AI
# ============================================================

def answer_repository_question(
    repository,
    files,
    question
):

    if client is None:

        return (
            "Gemini API key is not configured."
        )

    context = build_repository_context(
        repository,
        files
    )

    system_prompt = """
You are Gitora's repository assistant.

Answer questions about the supplied repository.

Use only the supplied repository information and source code.

Do not invent files, APIs, frameworks, databases,
authentication, or behavior.

If the answer cannot be determined from the supplied
repository, clearly say so.

Give a clear and useful technical answer.
"""

    user_prompt = f"""
Repository context:

{context}

USER QUESTION:

{question}
"""

    try:

        response = client.models.generate_content(

            model=MODEL,

            contents=(
                system_prompt
                + "\n\n"
                + user_prompt
            )
        )

        return safe_value(
            response.text,
            "Gemini returned no answer."
        )

    except Exception as e:

        print(
            "\n========== GITORA GEMINI CHAT ERROR =========="
        )

        print(
            f"Error type: {type(e).__name__}"
        )

        print(
            f"Error: {repr(e)}"
        )

        print(
            "===============================================\n"
        )

        return (
            "Gemini could not answer this question. "
            "Check the terminal for the exact error."
        )


# ============================================================
# REBUILD STRATEGIES
# ============================================================

def generate_rebuild_strategies(
    repository,
    files
):

    if client is None:

        return []

    context = build_repository_context(
        repository,
        files
    )

    system_prompt = """
You are a senior software architect.

Based only on the supplied repository, provide exactly
3 practical ways to rebuild or improve the project.

Return ONLY valid JSON:

{
    "rebuild_strategies": [
        {
            "title": "",
            "description": "",
            "technology": [],
            "advantages": [],
            "estimated_time": ""
        }
    ]
}
"""

    result = call_gemini_json(
        system_prompt,
        context
    )

    if not isinstance(result, dict):

        return []

    strategies = normalize_list(
        result.get("rebuild_strategies")
    )

    return strategies[:3]