# ============================================================
# GITORA AI SERVICE
# Gemini SDK + Interactions API
# ============================================================

import os
import json
import re
import time
import logging

from dotenv import load_dotenv
from google import genai

load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# Current production model.
# Can be overridden from Render environment variables.
MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.8-flash"
).strip()

# Safe fallback models.
GEMINI_MODELS = []

for model_name in [
    MODEL,
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]:
    if model_name and model_name not in GEMINI_MODELS:
        GEMINI_MODELS.append(model_name)


# ============================================================
# CLIENT
# ============================================================

_client = None


def get_gemini_client():
    """
    Create the Gemini client lazily.

    This prevents application startup from failing if the
    environment variable is temporarily unavailable.
    """

    global _client

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY is missing from the environment."
        )

    if _client is None:
        _client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options={
                "api_version": "v1"
            }
        )

    return _client


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
# JSON EXTRACTION
# ============================================================

def extract_json(text):
    """
    Extract JSON even if a model accidentally surrounds it
    with markdown fences or explanatory text.
    """

    if not text:
        return None

    text = text.strip()

    # Remove markdown fences.
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

    # Try to locate an object.
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
# EMPTY STRUCTURES
# ============================================================

def empty_file_analysis():
    return {
        "file": "",
        "summary": "",
        "purpose": "",
        "why_it_exists": "",
        "what_breaks_without_it": "",
        "important_functions": [],
        "dependencies": [],
        "connections": [],
        "issues": [],
        "improvements": []
    }


def empty_analysis():
    return {
        "project_summary": "",
        "technology_stack": [],
        "architecture": {},
        "dependencies": [],
        "database": [],
        "authentication": [],
        "important_requests": [],
        "routing": [],
        "run_instructions": [],
        "estimated_development_time": "",
        "folder_structure": [],
        "file_analysis": [],
        "rebuild_options": []
    }


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_file_analysis(data):

    result = empty_file_analysis()

    if not isinstance(data, dict):
        return result

    result["file"] = safe_value(
        data.get("file")
        or data.get("filename")
        or data.get("path")
    )

    result["summary"] = safe_value(
        data.get("summary")
    )

    result["purpose"] = safe_value(
        data.get("purpose")
    )

    result["why_it_exists"] = safe_value(
        data.get("why_it_exists")
        or data.get("why")
    )

    result["what_breaks_without_it"] = safe_value(
        data.get("what_breaks_without_it")
        or data.get("without_it")
    )

    result["important_functions"] = normalize_list(
        data.get("important_functions")
        or data.get("functions")
    )

    result["dependencies"] = normalize_list(
        data.get("dependencies")
    )

    result["connections"] = normalize_list(
        data.get("connections")
    )

    result["issues"] = normalize_list(
        data.get("issues")
    )

    result["improvements"] = normalize_list(
        data.get("improvements")
    )

    return result


def normalize_analysis(data):

    result = empty_analysis()

    if not isinstance(data, dict):
        return result

    result["project_summary"] = safe_value(
        data.get("project_summary")
        or data.get("summary")
    )

    result["technology_stack"] = normalize_list(
        data.get("technology_stack")
        or data.get("tech_stack")
    )

    result["architecture"] = (
        data.get("architecture")
        if isinstance(data.get("architecture"), dict)
        else {}
    )

    result["dependencies"] = normalize_list(
        data.get("dependencies")
    )

    result["database"] = normalize_list(
        data.get("database")
    )

    result["authentication"] = normalize_list(
        data.get("authentication")
    )

    result["important_requests"] = normalize_list(
        data.get("important_requests")
        or data.get("api_endpoints")
    )

    result["routing"] = normalize_list(
        data.get("routing")
        or data.get("routes")
    )

    result["run_instructions"] = normalize_list(
        data.get("run_instructions")
        or data.get("run")
    )

    result["estimated_development_time"] = safe_value(
        data.get("estimated_development_time")
        or data.get("estimated_time")
    )

    result["folder_structure"] = normalize_list(
        data.get("folder_structure")
    )

    raw_files = data.get("file_analysis", [])

    if isinstance(raw_files, list):

        result["file_analysis"] = [
            normalize_file_analysis(item)
            for item in raw_files
            if isinstance(item, dict)
        ]

    result["rebuild_options"] = normalize_list(
        data.get("rebuild_options")
    )

    return result


# ============================================================
# REPOSITORY CONTEXT
# ============================================================

def build_repository_context(files):

    blocks = []

    for file in files or []:

        path = file.get("path", "")

        if not path:
            continue

        content = file.get("content", "")

        if content is None:
            content = ""

        content = str(content)

        # Prevent huge prompts.
        content = content[:30000]

        blocks.append(
            f"""
==================================================
FILE: {path}
==================================================

{content}
"""
        )

    return "\n".join(blocks)


# ============================================================
# JSON SCHEMA
# ============================================================

REPOSITORY_SCHEMA = {
    "type": "object",
    "properties": {

        "project_summary": {
            "type": "string"
        },

        "technology_stack": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },

        "architecture": {
            "type": "object"
        },

        "dependencies": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },

        "database": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },

        "authentication": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },

        "important_requests": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },

        "routing": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },

        "run_instructions": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },

        "estimated_development_time": {
            "type": "string"
        },

        "folder_structure": {
            "type": "array",
            "items": {
                "type": "string"
            }
        },

        "file_analysis": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string"
                    },
                    "summary": {
                        "type": "string"
                    },
                    "purpose": {
                        "type": "string"
                    },
                    "why_it_exists": {
                        "type": "string"
                    },
                    "what_breaks_without_it": {
                        "type": "string"
                    },
                    "important_functions": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "dependencies": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "connections": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "issues": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "improvements": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    }
                },
                "required": [
                    "file",
                    "summary",
                    "purpose",
                    "why_it_exists",
                    "what_breaks_without_it"
                ]
            }
        },

        "rebuild_options": {
            "type": "array",
            "items": {
                "type": "string"
            }
        }
    },

    "required": [
        "project_summary",
        "technology_stack",
        "architecture",
        "dependencies",
        "database",
        "authentication",
        "important_requests",
        "routing",
        "run_instructions",
        "estimated_development_time",
        "folder_structure",
        "file_analysis",
        "rebuild_options"
    ]
}


# ============================================================
# GEMINI INTERACTIONS CALL
# ============================================================

def call_gemini_json(prompt):

    if not GEMINI_API_KEY:

        raise RuntimeError(
            "GEMINI_API_KEY is not configured on the server."
        )

    client = get_gemini_client()

    last_error = None

    for attempt, model_name in enumerate(
        GEMINI_MODELS[:3],
        start=1
    ):

        try:

            logger.info(
                "Gemini request: model=%s attempt=%s",
                model_name,
                attempt
            )

            interaction = client.interactions.create(

                model=model_name,

                input=prompt,

                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": REPOSITORY_SCHEMA
                },

                generation_config={
                    "max_output_tokens": 12000
                }
            )

            text = getattr(
                interaction,
                "output_text",
                None
            )

            if not text:
                raise RuntimeError(
                    "Gemini returned an empty response."
                )

            data = extract_json(text)

            if data is None:
                raise RuntimeError(
                    "Gemini returned invalid JSON."
                )

            logger.info(
                "Gemini request succeeded with %s",
                model_name
            )

            return data

        except Exception as exc:

            last_error = exc

            logger.exception(
                "Gemini request failed with model %s",
                model_name
            )

            # Do not retry configuration/authentication
            # failures against another model.
            message = str(exc).lower()

            permanent_error_terms = [
                "api key",
                "permission",
                "unauthorized",
                "authentication",
                "invalid argument",
                "not found"
            ]

            if any(
                term in message
                for term in permanent_error_terms
            ):
                break

            if attempt < min(3, len(GEMINI_MODELS)):
                time.sleep(1)

    raise RuntimeError(
        f"Gemini AI request failed: {last_error}"
    )


# ============================================================
# FULL REPOSITORY ANALYSIS
# ============================================================

def analyze_repository(repository, files):

    repository_name = (
        repository.get("full_name")
        or repository.get("name")
        or "Unknown repository"
    )

    context = build_repository_context(files)

    prompt = f"""
You are Gitora, an expert software repository analyst.

Analyze the repository below using ONLY the supplied repository
information and source files.

Do not invent files, routes, APIs, databases, authentication,
dependencies, or functionality that are not supported by the
source.

Repository:
{repository_name}

Repository description:
{repository.get("description", "")}

Repository language:
{repository.get("language", "")}

Repository URL:
{repository.get("html_url", "")}

SOURCE FILES:

{context}

Produce a complete technical analysis.

For every important source file explain:

1. What the file does
2. Why it exists
3. Important functions/classes
4. Dependencies
5. Connections to other files
6. What breaks if it is removed
7. Problems or risks
8. Improvements

Also identify:

- project summary
- technology stack
- architecture
- database
- authentication
- important API requests
- routing
- run instructions
- folder structure
- realistic development time
- three practical ways to rebuild the project

Return ONLY JSON matching the requested schema.
"""

    raw = call_gemini_json(prompt)

    return normalize_analysis(raw)


# ============================================================
# SINGLE FILE ANALYSIS
# ============================================================

def analyze_single_file(
    repository,
    file_path,
    content
):

    content = (content or "")[:50000]

    prompt = f"""
You are Gitora, an expert software engineer.

Analyze this single repository file.

Repository:
{repository.get("full_name", "")}

File:
{file_path}

SOURCE:

{content}

Explain:

- what the file does
- why it exists
- important functions/classes
- dependencies
- connections to other files
- what breaks if removed
- issues
- improvements

Return JSON matching this structure:

{{
  "file": "{file_path}",
  "summary": "",
  "purpose": "",
  "why_it_exists": "",
  "what_breaks_without_it": "",
  "important_functions": [],
  "dependencies": [],
  "connections": [],
  "issues": [],
  "improvements": []
}}
"""

    client = get_gemini_client()

    last_error = None

    for model_name in GEMINI_MODELS[:3]:

        try:

            interaction = client.interactions.create(

                model=model_name,

                input=prompt,

                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "file": {
                                "type": "string"
                            },
                            "summary": {
                                "type": "string"
                            },
                            "purpose": {
                                "type": "string"
                            },
                            "why_it_exists": {
                                "type": "string"
                            },
                            "what_breaks_without_it": {
                                "type": "string"
                            },
                            "important_functions": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "dependencies": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "connections": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "issues": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "improvements": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            }
                        },
                        "required": [
                            "file",
                            "summary",
                            "purpose",
                            "why_it_exists",
                            "what_breaks_without_it"
                        ]
                    }
                },

                generation_config={
                    "max_output_tokens": 6000
                }
            )

            text = getattr(
                interaction,
                "output_text",
                None
            )

            data = extract_json(text)

            if data is None:
                raise RuntimeError(
                    "Invalid JSON returned for file analysis."
                )

            return normalize_file_analysis(data)

        except Exception as exc:

            last_error = exc

            logger.exception(
                "Single-file Gemini analysis failed: %s",
                file_path
            )

    raise RuntimeError(
        f"Gemini file analysis failed: {last_error}"
    )


# ============================================================
# ASK GITORA AI
# ============================================================

def answer_repository_question(
    repository,
    files,
    question
):

    context = build_repository_context(files)

    prompt = f"""
You are Gitora, an AI assistant specialized in understanding
software repositories.

Repository:
{repository.get("full_name", "")}

Source files:

{context}

User question:

{question}

Answer using the repository source above.

Rules:

- Do not invent implementation details.
- If the source does not contain enough information, say so.
- Mention relevant filenames when useful.
- Give practical technical answers.
"""

    client = get_gemini_client()

    last_error = None

    for model_name in GEMINI_MODELS[:3]:

        try:

            interaction = client.interactions.create(

                model=model_name,

                input=prompt,

                generation_config={
                    "max_output_tokens": 5000
                }
            )

            answer = getattr(
                interaction,
                "output_text",
                None
            )

            if answer:
                return answer.strip()

            raise RuntimeError(
                "Gemini returned an empty answer."
            )

        except Exception as exc:

            last_error = exc

            logger.exception(
                "Repository question failed."
            )

    raise RuntimeError(
        f"Gitora AI question failed: {last_error}"
    )


# ============================================================
# REBUILD STRATEGIES
# ============================================================

def generate_rebuild_strategies(
    repository,
    files
):

    context = build_repository_context(files)

    prompt = f"""
You are Gitora.

Analyze this repository and propose three realistic ways to
rebuild the same project.

Repository:
{repository.get("full_name", "")}

Source:

{context}

Return JSON:

{{
    "rebuild_options": [
        "Option 1",
        "Option 2",
        "Option 3"
    ]
}}
"""

    raw = call_gemini_json(prompt)

    return {
        "rebuild_options": normalize_list(
            raw.get("rebuild_options")
            if isinstance(raw, dict)
            else []
        )
    }