# ============================================================
# GITORA AI SERVICE
# Remote OpenAI-Compatible AI Backend
# Gemini / Ollama NOT required
# ============================================================

import os
import json
import re
import logging
import requests

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

AI_BASE_URL = os.getenv("AI_BASE_URL", "").strip().rstrip("/")
AI_API_KEY = os.getenv("AI_API_KEY", "").strip()
AI_MODEL = os.getenv("AI_MODEL", "").strip()

AI_TIMEOUT = int(os.getenv("AI_TIMEOUT", "120"))

MAX_FILE_CHARS = int(
    os.getenv("AI_MAX_FILE_CHARS", "16000")
)

MAX_CONTEXT_CHARS = int(
    os.getenv("AI_MAX_CONTEXT_CHARS", "90000")
)


# ============================================================
# BASIC HELPERS
# ============================================================

def safe_value(value, default=""):
    if value is None:
        return default

    if isinstance(value, str):
        return value.strip()

    return value


def normalize_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return [
            str(item).strip()
            for item in value
            if str(item).strip()
        ]

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return []

        return [value]

    return [str(value)]


def extract_json(text):
    """
    Extract JSON from an AI response.

    Supports:
    - plain JSON
    - ```json ... ```
    - ``` ... ```
    - JSON surrounded by explanatory text
    """

    if not text:
        return None

    text = str(text).strip()

    # --------------------------------------------------------
    # Remove markdown code fences
    # --------------------------------------------------------

    fenced = re.search(
        r"```(?:json)?\s*(.*?)\s*```",
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

    if fenced:
        text = fenced.group(1).strip()

    # --------------------------------------------------------
    # Direct JSON
    # --------------------------------------------------------

    try:
        return json.loads(text)
    except Exception:
        pass

    # --------------------------------------------------------
    # Find first JSON object
    # --------------------------------------------------------

    start = text.find("{")

    if start != -1:

        depth = 0
        in_string = False
        escaped = False

        for index in range(start, len(text)):

            char = text[index]

            if escaped:
                escaped = False
                continue

            if char == "\\":
                escaped = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == "{":
                depth += 1

            elif char == "}":
                depth -= 1

                if depth == 0:

                    candidate = text[
                        start:index + 1
                    ]

                    try:
                        return json.loads(candidate)
                    except Exception:
                        break

    return None


# ============================================================
# EMPTY ANALYSIS STRUCTURES
# ============================================================

def empty_file_analysis(path=""):
    return {
        "path": path,
        "summary": "No AI analysis available.",
        "does": [],
        "why": "",
        "role": "",
        "dependencies": [],
        "requests": [],
        "breaks": []
    }


def empty_analysis():
    return {
        "project_summary": "",
        "technology_stack": [],
        "architecture": "",
        "dependencies": [],
        "database": "",
        "authentication": "",
        "important_requests": [],
        "rebuild_options": [],
        "file_analysis": [],
        "estimated_time": "",
        "routing": [],
        "run_instructions": [],
        "folder_structure": ""
    }


# ============================================================
# NORMALIZE FILE ANALYSIS
# ============================================================

def normalize_file_analysis(item):

    if not isinstance(item, dict):
        return empty_file_analysis()

    result = empty_file_analysis(
        safe_value(item.get("path"))
    )

    result["summary"] = safe_value(
        item.get("summary")
        or item.get("description")
        or item.get("what_it_does"),
        "No description available."
    )

    result["does"] = normalize_list(
        item.get("does")
        or item.get("functionality")
        or item.get("what_it_does")
    )

    result["why"] = safe_value(
        item.get("why")
        or item.get("importance")
    )

    result["role"] = safe_value(
        item.get("role")
        or item.get("purpose")
    )

    result["dependencies"] = normalize_list(
        item.get("dependencies")
    )

    result["requests"] = normalize_list(
        item.get("requests")
        or item.get("api_requests")
    )

    result["breaks"] = normalize_list(
        item.get("breaks")
        or item.get("failure_points")
        or item.get("risks")
    )

    return result


# ============================================================
# NORMALIZE OVERALL ANALYSIS
# ============================================================

def normalize_analysis(data):

    if not isinstance(data, dict):
        return empty_analysis()

    result = empty_analysis()

    result["project_summary"] = safe_value(
        data.get("project_summary")
        or data.get("summary")
        or data.get("project_understanding")
    )

    result["technology_stack"] = normalize_list(
        data.get("technology_stack")
        or data.get("tech_stack")
    )

    result["architecture"] = safe_value(
        data.get("architecture")
    )

    result["dependencies"] = normalize_list(
        data.get("dependencies")
    )

    result["database"] = safe_value(
        data.get("database")
        or data.get("database_details")
    )

    result["authentication"] = safe_value(
        data.get("authentication")
        or data.get("auth")
    )

    result["important_requests"] = normalize_list(
        data.get("important_requests")
        or data.get("api_requests")
        or data.get("important_api_requests")
    )

    rebuild = data.get("rebuild_options")

    if not isinstance(rebuild, list):
        rebuild = []

    result["rebuild_options"] = rebuild

    file_analysis = data.get("file_analysis")

    if not isinstance(file_analysis, list):
        file_analysis = []

    result["file_analysis"] = [
        normalize_file_analysis(item)
        for item in file_analysis
    ]

    result["estimated_time"] = safe_value(
        data.get("estimated_time")
        or data.get("development_time")
    )

    result["routing"] = normalize_list(
        data.get("routing")
        or data.get("routes")
    )

    result["run_instructions"] = normalize_list(
        data.get("run_instructions")
        or data.get("run")
    )

    result["folder_structure"] = safe_value(
        data.get("folder_structure")
    )

    return result


# ============================================================
# NORMALIZE REBUILD OPTIONS
# ============================================================

def normalize_rebuild_options(data):

    if isinstance(data, dict):
        data = data.get(
            "rebuild_options",
            data.get("options", [])
        )

    if not isinstance(data, list):
        return []

    normalized = []

    for item in data:

        if isinstance(item, str):

            normalized.append({
                "title": "Approach",
                "description": item,
                "stack": [],
                "architecture": "",
                "time": "",
                "pros": [],
                "cons": []
            })

            continue

        if not isinstance(item, dict):
            continue

        normalized.append({
            "title": safe_value(
                item.get("title")
                or item.get("name"),
                "Rebuild Approach"
            ),

            "description": safe_value(
                item.get("description")
                or item.get("summary")
            ),

            "stack": normalize_list(
                item.get("stack")
                or item.get("technology_stack")
            ),

            "architecture": safe_value(
                item.get("architecture")
            ),

            "time": safe_value(
                item.get("time")
                or item.get("estimated_time")
            ),

            "pros": normalize_list(
                item.get("pros")
            ),

            "cons": normalize_list(
                item.get("cons")
            )
        })

    return normalized


# ============================================================
# AI ENDPOINT
# ============================================================

def get_chat_endpoint():

    if not AI_BASE_URL:
        return ""

    if AI_BASE_URL.endswith(
        "/chat/completions"
    ):
        return AI_BASE_URL

    if AI_BASE_URL.endswith("/v1"):
        return (
            AI_BASE_URL
            + "/chat/completions"
        )

    return (
        AI_BASE_URL
        + "/v1/chat/completions"
    )


# ============================================================
# CALL REMOTE AI
# ============================================================

def call_ai(
    system_prompt,
    user_prompt,
    max_tokens=5000,
    temperature=0.1
):

    if not AI_BASE_URL:
        raise RuntimeError(
            "AI_BASE_URL is not configured."
        )

    if not AI_API_KEY:
        raise RuntimeError(
            "AI_API_KEY is not configured."
        )

    if not AI_MODEL:
        raise RuntimeError(
            "AI_MODEL is not configured."
        )

    endpoint = get_chat_endpoint()

    headers = {
        "Content-Type": "application/json",
        "Authorization": (
            f"Bearer {AI_API_KEY}"
        )
    }

    payload = {
        "model": AI_MODEL,

        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_prompt
            }
        ],

        "temperature": temperature,

        "max_tokens": max_tokens
    }

    try:

        response = requests.post(
            endpoint,
            headers=headers,
            json=payload,
            timeout=AI_TIMEOUT
        )

    except requests.RequestException as error:

        logger.exception(
            "REMOTE AI CONNECTION ERROR"
        )

        raise RuntimeError(
            "Unable to connect to the remote AI service."
        ) from error

    if response.status_code >= 400:

        try:
            error_data = response.json()

            error_message = (
                error_data.get("error", {})
                if isinstance(
                    error_data,
                    dict
                )
                else {}
            )

            if isinstance(
                error_message,
                dict
            ):
                error_message = (
                    error_message.get(
                        "message",
                        ""
                    )
                )

        except Exception:

            error_message = ""

        if not error_message:
            error_message = response.text[:500]

        logger.error(
            "AI PROVIDER ERROR %s: %s",
            response.status_code,
            error_message
        )

        raise RuntimeError(
            f"AI service returned "
            f"{response.status_code}: "
            f"{error_message}"
        )

    try:

        data = response.json()

    except ValueError as error:

        raise RuntimeError(
            "AI service returned invalid JSON."
        ) from error

    try:

        content = (
            data["choices"][0]
            ["message"]["content"]
        )

    except (
        KeyError,
        IndexError,
        TypeError
    ) as error:

        logger.error(
            "Unexpected AI response: %s",
            data
        )

        raise RuntimeError(
            "AI service returned an unexpected response."
        ) from error

    # Some APIs may return structured content.
    if isinstance(content, list):

        parts = []

        for item in content:

            if isinstance(item, dict):

                text_part = item.get(
                    "text",
                    ""
                )

                if text_part:
                    parts.append(
                        str(text_part)
                    )

            elif isinstance(item, str):

                parts.append(item)

        content = "\n".join(parts)

    return str(content).strip()


# ============================================================
# REPOSITORY CONTEXT
# ============================================================

def build_repository_context(
    repository,
    source_files
):

    repository = (
        repository
        if isinstance(repository, dict)
        else {}
    )

    lines = []

    lines.append(
        f"Repository: "
        f"{repository.get('full_name', '')}"
    )

    lines.append(
        f"Description: "
        f"{repository.get('description', '')}"
    )

    lines.append(
        f"Primary language: "
        f"{repository.get('language', '')}"
    )

    lines.append(
        f"Default branch: "
        f"{repository.get('default_branch', '')}"
    )

    lines.append("")
    lines.append("SOURCE FILES")
    lines.append("")

    total_chars = 0

    for source in source_files or []:

        if not isinstance(source, dict):
            continue

        path = safe_value(
            source.get("path")
        )

        content = safe_value(
            source.get("content")
        )

        if not path:
            continue

        if not content:
            content = "[No readable content]"

        content = content[
            :MAX_FILE_CHARS
        ]

        block = (
            "\n"
            + "=" * 70
            + "\n"
            + f"FILE: {path}\n"
            + "=" * 70
            + "\n"
            + content
            + "\n"
        )

        remaining = (
            MAX_CONTEXT_CHARS
            - total_chars
        )

        if remaining <= 0:
            break

        if len(block) > remaining:

            block = block[
                :remaining
            ]

        lines.append(block)

        total_chars += len(block)

    return "\n".join(lines)


# ============================================================
# OVERALL REPOSITORY ANALYSIS
# ============================================================

def analyze_repository(
    repository,
    source_files
):

    context = build_repository_context(
        repository,
        source_files
    )

    system_prompt = """
You are Gitora AI, a senior software architect
and repository analysis assistant.

Analyze ONLY the repository information and source
code provided by the user.

Do not invent files, frameworks, APIs, database
systems, authentication mechanisms, routes, or
dependencies that are not supported by the source.

If something cannot be determined, explicitly say
that it cannot be determined from the supplied files.

Return ONLY valid JSON.

Use exactly these top-level keys:

{
  "project_summary": "string",
  "technology_stack": ["string"],
  "architecture": "string",
  "dependencies": ["string"],
  "database": "string",
  "authentication": "string",
  "important_requests": ["string"],
  "rebuild_options": [],
  "file_analysis": [],
  "estimated_time": "string",
  "routing": ["string"],
  "run_instructions": ["string"],
  "folder_structure": "string"
}

For file_analysis, create one object for each
important supplied source file:

{
  "path": "string",
  "summary": "string",
  "does": ["string"],
  "why": "string",
  "role": "string",
  "dependencies": ["string"],
  "requests": ["string"],
  "breaks": ["string"]
}

For important_requests, identify meaningful HTTP/API/
external-service requests found in the code.

For estimated_time, give a realistic approximate
development time based on the actual project.

For routing, identify actual routes/endpoints found
in the source.

For run_instructions, provide practical steps supported
by the files.

Keep the analysis precise and evidence-based.
"""

    user_prompt = f"""
Analyze this GitHub repository.

Repository metadata:
{json.dumps(repository, indent=2)}

Repository source:

{context}

Return valid JSON only.
"""

    raw = call_ai(
        system_prompt,
        user_prompt,
        max_tokens=7000,
        temperature=0.1
    )

    parsed = extract_json(raw)

    if not isinstance(parsed, dict):

        raise RuntimeError(
            "AI returned an invalid repository analysis."
        )

    return normalize_analysis(parsed)


# ============================================================
# SINGLE FILE ANALYSIS
# ============================================================

def analyze_single_file(
    repository,
    file_path,
    content
):

    system_prompt = """
You are Gitora AI, an expert software engineer.

Analyze the supplied source file.

Use ONLY the supplied source.

Do not invent functionality.

Return ONLY valid JSON with exactly:

{
  "path": "string",
  "summary": "string",
  "does": ["string"],
  "why": "string",
  "role": "string",
  "dependencies": ["string"],
  "requests": ["string"],
  "breaks": ["string"]
}
"""

    user_prompt = f"""
Repository:
{json.dumps(repository or {}, indent=2)}

File:
{file_path}

Source code:

{str(content or '')[:MAX_FILE_CHARS]}

Return valid JSON only.
"""

    raw = call_ai(
        system_prompt,
        user_prompt,
        max_tokens=2500,
        temperature=0.1
    )

    parsed = extract_json(raw)

    if not isinstance(parsed, dict):

        raise RuntimeError(
            "AI returned invalid file analysis."
        )

    return normalize_file_analysis(parsed)


# ============================================================
# REBUILD STRATEGIES
# ============================================================

def generate_rebuild_strategies(
    repository,
    source_files
):

    context = build_repository_context(
        repository,
        source_files
    )

    system_prompt = """
You are a senior software architect.

Based ONLY on the supplied repository,
create three genuinely different ways to rebuild
the project.

Return ONLY valid JSON:

{
  "rebuild_options": [
    {
      "title": "string",
      "description": "string",
      "stack": ["string"],
      "architecture": "string",
      "time": "string",
      "pros": ["string"],
      "cons": ["string"]
    }
  ]
}

The three approaches must be meaningfully different.

Do not invent requirements that are not supported
by the repository.
"""

    user_prompt = f"""
Repository:
{json.dumps(repository or {}, indent=2)}

Source:

{context}

Return valid JSON only.
"""

    raw = call_ai(
        system_prompt,
        user_prompt,
        max_tokens=4500,
        temperature=0.2
    )

    parsed = extract_json(raw)

    if not parsed:
        raise RuntimeError(
            "AI returned invalid rebuild options."
        )

    return {
        "rebuild_options":
            normalize_rebuild_options(parsed)
    }


# ============================================================
# ASK GITORA AI
# ============================================================

def answer_repository_question(
    repository,
    source_files,
    question
):

    context = build_repository_context(
        repository,
        source_files
    )

    system_prompt = """
You are Gitora AI.

Answer questions about a GitHub repository
using ONLY the supplied repository metadata
and source code.

Do not invent information.

If the source does not provide enough evidence,
say so clearly.

Give a concise but useful technical answer.
"""

    user_prompt = f"""
Repository:
{json.dumps(repository or {}, indent=2)}

Repository source:

{context}

Question:
{question}
"""

    return call_ai(
        system_prompt,
        user_prompt,
        max_tokens=1800,
        temperature=0.2
    )


# ============================================================
# AI HEALTH CHECK
# ============================================================

def test_ai_connection():

    if not AI_BASE_URL:
        return {
            "ok": False,
            "message": "AI_BASE_URL is missing."
        }

    if not AI_API_KEY:
        return {
            "ok": False,
            "message": "AI_API_KEY is missing."
        }

    if not AI_MODEL:
        return {
            "ok": False,
            "message": "AI_MODEL is missing."
        }

    try:

        response = call_ai(
            """
You are a connection test.
Reply with exactly:
OK
""",
            "Respond with exactly OK.",
            max_tokens=10,
            temperature=0
        )

        return {
            "ok": True,
            "message": response,
            "model": AI_MODEL
        }

    except Exception as error:

        return {
            "ok": False,
            "message": str(error),
            "model": AI_MODEL
        }