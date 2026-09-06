import os
import json
import re
import time
import requests

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# GEMINI CONFIGURATION
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.6-flash"
).strip()


# Keep the fallback list controlled.
# The configured model is always tried first.
GEMINI_MODELS = []

for model_name in [
    MODEL,
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite"
]:
    model_name = str(model_name).strip()

    if model_name and model_name not in GEMINI_MODELS:
        GEMINI_MODELS.append(model_name)


# ============================================================
# GEMINI URL
# ============================================================

def get_gemini_url(model_name):
    return (
        "https://generativelanguage.googleapis.com/"
        f"v1beta/models/{model_name}:generateContent"
    )


# ============================================================
# SAFE HELPERS
# ============================================================

def safe_value(value, default="None identified."):
    if value is None:
        return default

    if isinstance(value, str):
        value = value.strip()
        return value if value else default

    if isinstance(value, (int, float, bool)):
        return str(value)

    if isinstance(value, list):
        values = []

        for item in value:
            if isinstance(item, dict):
                try:
                    values.append(
                        json.dumps(
                            item,
                            ensure_ascii=False
                        )
                    )
                except Exception:
                    continue
            else:
                text = str(item).strip()

                if text:
                    values.append(text)

        return ", ".join(values) if values else default

    if isinstance(value, dict):
        try:
            return json.dumps(
                value,
                ensure_ascii=False
            )
        except Exception:
            return default

    text = str(value).strip()

    return text if text else default


def normalize_list(value):

    if value is None:
        return []

    if isinstance(value, list):

        result = []

        for item in value:

            if isinstance(item, dict):
                text = safe_value(
                    item,
                    ""
                )
            else:
                text = str(item).strip()

            if text:
                result.append(text)

        return result

    if isinstance(value, dict):

        result = []

        for key, item in value.items():

            text = (
                f"{key}: "
                f"{safe_value(item, '')}"
            ).strip()

            if text:
                result.append(text)

        return result

    if isinstance(value, str):

        value = value.strip()

        if not value:
            return []

        try:

            parsed = json.loads(value)

            if isinstance(parsed, list):
                return normalize_list(parsed)

        except Exception:
            pass

        if "\n" in value:

            return [
                line.strip("-• ").strip()
                for line in value.splitlines()
                if line.strip("-• ").strip()
            ]

        if ";" in value:

            return [
                item.strip()
                for item in value.split(";")
                if item.strip()
            ]

        return [value]

    return [str(value).strip()]


# ============================================================
# REPOSITORY CONTEXT
# ============================================================

def build_repository_context(repository, files):

    repository = repository or {}

    repo_name = safe_value(
        repository.get("name"),
        "Unknown repository"
    )

    repo_full_name = safe_value(
        repository.get("full_name"),
        repo_name
    )

    repo_description = safe_value(
        repository.get("description"),
        "No repository description available."
    )

    context = f"""
Repository Name:
{repo_name}

Full Repository:
{repo_full_name}

Description:
{repo_description}

Files:
"""

    if not files:
        context += "No files were supplied.\n"
        return context

    for file in files:

        if not isinstance(file, dict):
            continue

        path = safe_value(
            file.get("path"),
            "Unknown file"
        )

        content = file.get(
            "content",
            ""
        )

        if content is None:
            content = ""

        content = str(content)

        # Prevent extremely large Gemini requests.
        if len(content) > 30000:

            content = (
                content[:30000]
                + "\n\n[FILE CONTENT TRUNCATED]"
            )

        context += f"""
--------------------------------------------------
FILE: {path}
--------------------------------------------------
{content}

"""

    return context


# ============================================================
# EMPTY ANALYSIS
# ============================================================

def empty_analysis(
    message="AI analysis unavailable."
):

    return {

        "project_summary": message,

        "technology_stack": [],

        "architecture": message,

        "dependencies": [],

        "database": message,

        "authentication": message,

        "important_requests": [],

        "file_analysis": [],

        "rebuild_options": [],

        "estimated_development_time":
            "Not identified.",

        "routing": [],

        "run_instructions": [],

        "folder_structure": message
    }


def empty_file_analysis(
    file_path="",
    message="AI analysis unavailable."
):

    return {

        "file": file_path,

        "what_it_does": message,

        "why_it_exists": message,

        "website_role": message,

        "dependencies": [],

        "important_requests": [],

        "what_breaks": message,

        "what_breaks_without_it": message,

        "connections": [],

        "important_code": []
    }


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(text):

    if not text:
        return None

    if not isinstance(text, str):
        text = str(text)

    text = text.strip()

    if not text:
        return None

    # Remove markdown fences.
    text = re.sub(
        r"```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"```\s*",
        "",
        text
    )

    text = text.strip()

    # Direct JSON.
    try:
        return json.loads(text)

    except Exception:
        pass

    # JSON object.
    first_object = text.find("{")
    last_object = text.rfind("}")

    if (
        first_object != -1
        and last_object != -1
        and last_object > first_object
    ):

        candidate = text[
            first_object:last_object + 1
        ]

        try:
            return json.loads(candidate)

        except Exception:
            pass

    # JSON array.
    first_array = text.find("[")
    last_array = text.rfind("]")

    if (
        first_array != -1
        and last_array != -1
        and last_array > first_array
    ):

        candidate = text[
            first_array:last_array + 1
        ]

        try:
            return json.loads(candidate)

        except Exception:
            pass

    return None


# ============================================================
# FILE NORMALIZATION
# ============================================================

def normalize_file_analysis(data):

    if not isinstance(data, dict):

        return empty_file_analysis(
            message=(
                "Gemini returned an invalid "
                "file analysis format."
            )
        )

    file_path = safe_value(
        data.get("file")
        or data.get("file_path")
        or data.get("filename"),
        ""
    )

    result = {

        "file": file_path,

        "what_it_does": safe_value(
            data.get("what_it_does")
            or data.get("description")
            or data.get("purpose")
        ),

        "why_it_exists": safe_value(
            data.get("why_it_exists")
            or data.get("why")
            or data.get("purpose_reason")
        ),

        "website_role": safe_value(
            data.get("website_role")
            or data.get("how_it_helps")
            or data.get("role")
            or data.get("connections")
        ),

        "dependencies": normalize_list(
            data.get("dependencies")
            or data.get("required_files")
            or data.get("depends_on")
        ),

        "important_requests": normalize_list(
            data.get("important_requests")
            or data.get("api_requests")
            or data.get("requests")
            or data.get("endpoints")
        ),

        "what_breaks": safe_value(
            data.get("what_breaks")
            or data.get("what_breaks_without_it")
            or data.get("impact")
        )
    }

    result["what_breaks_without_it"] = (
        result["what_breaks"]
    )

    result["connections"] = (
        result["important_requests"]
    )

    result["important_code"] = normalize_list(
        data.get("important_code")
        or data.get("key_code")
        or []
    )

    return result


# ============================================================
# ANALYSIS NORMALIZATION
# ============================================================

def normalize_analysis(data):

    if not isinstance(data, dict):

        return empty_analysis(
            "Gemini returned an invalid analysis format."
        )

    result = empty_analysis()

    result["project_summary"] = safe_value(
        data.get("project_summary")
        or data.get("summary")
        or data.get("overview")
    )

    result["technology_stack"] = normalize_list(
        data.get("technology_stack")
        or data.get("tech_stack")
        or data.get("technologies")
    )

    result["architecture"] = safe_value(
        data.get("architecture")
        or data.get("system_architecture")
    )

    result["dependencies"] = normalize_list(
        data.get("dependencies")
        or data.get("libraries")
        or data.get("packages")
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
        or data.get("requests")
        or data.get("endpoints")
    )

    result["routing"] = normalize_list(
        data.get("routing")
        or data.get("routes")
        or data.get("routing_structure")
    )

    result["run_instructions"] = normalize_list(
        data.get("run_instructions")
        or data.get("run_steps")
        or data.get("installation")
    )

    result["estimated_development_time"] = safe_value(
        data.get("estimated_development_time")
        or data.get("development_time")
    )

    result["folder_structure"] = safe_value(
        data.get("folder_structure")
        or data.get("structure")
    )

    # --------------------------------------------------------
    # FILE ANALYSIS
    # --------------------------------------------------------

    file_analysis = data.get(
        "file_analysis",
        []
    )

    if not isinstance(file_analysis, list):
        file_analysis = []

    result["file_analysis"] = [
        normalize_file_analysis(item)
        for item in file_analysis
        if isinstance(item, dict)
    ]

    # --------------------------------------------------------
    # REBUILD OPTIONS
    # --------------------------------------------------------

    rebuild_options = (
        data.get("rebuild_options")
        or data.get("rebuild_ways")
        or data.get("ways_to_rebuild")
        or []
    )

    if not isinstance(rebuild_options, list):
        rebuild_options = []

    normalized_rebuild = []

    for item in rebuild_options:

        if isinstance(item, dict):

            normalized_rebuild.append({

                "title": safe_value(
                    item.get("title")
                    or item.get("name")
                    or item.get("approach")
                ),

                "description": safe_value(
                    item.get("description")
                    or item.get("details")
                ),

                "technology": normalize_list(
                    item.get("technology")
                    or item.get("technologies")
                    or item.get("stack")
                ),

                "estimated_time": safe_value(
                    item.get("estimated_time")
                    or item.get("time")
                )
            })

        else:

            normalized_rebuild.append({

                "title": safe_value(item),

                "description":
                    "None identified.",

                "technology": [],

                "estimated_time":
                    "Not identified."
            })

    result["rebuild_options"] = (
        normalized_rebuild
    )

    return result


# ============================================================
# GEMINI API CALL
# ============================================================

def call_gemini_json(prompt):

    print()
    print("========================================")
    print("🔥 GEMINI CONNECTION CHECK")
    print("========================================")

    if not GEMINI_API_KEY:

        print("❌ GEMINI_API_KEY IS MISSING")
        print(
            "Render environment variable "
            "GEMINI_API_KEY was not found."
        )
        print("========================================")

        return None

    print("✅ GEMINI_API_KEY FOUND")
    print(
        "Configured model:",
        MODEL
    )

    print(
        "Models to try:",
        GEMINI_MODELS
    )

    print("========================================")
    print()

    payload = {

        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],

        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType":
                "application/json"
        }
    }

    headers = {

        "Content-Type":
            "application/json",

        "x-goog-api-key":
            GEMINI_API_KEY
    }

    for index, model_name in enumerate(
        GEMINI_MODELS
    ):

        url = get_gemini_url(
            model_name
        )

        print()
        print("========================================")
        print("🔥 GEMINI AI REQUEST")
        print("========================================")
        print(
            "Model:",
            model_name
        )
        print(
            "Attempt:",
            index + 1,
            "/",
            len(GEMINI_MODELS)
        )
        print(
            "URL:",
            url
        )

        try:

            response = requests.post(

                url,

                headers=headers,

                json=payload,

                timeout=120
            )

            print(
                "Gemini status:",
                response.status_code
            )

            # ------------------------------------------------
            # SUCCESS
            # ------------------------------------------------

            if response.status_code == 200:

                try:

                    response_data = (
                        response.json()
                    )

                except Exception as error:

                    print(
                        "❌ Invalid Gemini HTTP JSON:",
                        type(error).__name__,
                        str(error)
                    )

                    continue

                candidates = (
                    response_data.get(
                        "candidates",
                        []
                    )
                )

                if not candidates:

                    print(
                        "❌ Gemini returned no candidates."
                    )

                    print(
                        "Response:",
                        response.text[:3000]
                    )

                    continue

                candidate = candidates[0]

                content = candidate.get(
                    "content",
                    {}
                )

                parts = content.get(
                    "parts",
                    []
                )

                if not parts:

                    print(
                        "❌ Gemini returned no parts."
                    )

                    print(
                        "Response:",
                        response.text[:3000]
                    )

                    continue

                text = parts[0].get(
                    "text",
                    ""
                )

                if not text:

                    print(
                        "❌ Gemini returned empty text."
                    )

                    continue

                parsed = extract_json(
                    text
                )

                if parsed is None:

                    print(
                        "❌ Gemini JSON extraction failed."
                    )

                    print(
                        "Gemini text:",
                        text[:3000]
                    )

                    continue

                print()
                print("========================================")
                print("✅ GEMINI AI SUCCESS")
                print("========================================")
                print(
                    "Working model:",
                    model_name
                )
                print("========================================")
                print()

                return parsed

            # ------------------------------------------------
            # 503
            # ------------------------------------------------

            if response.status_code == 503:

                print(
                    "⚠️ Gemini model temporarily unavailable."
                )

                print(
                    response.text[:2000]
                )

                if index < len(
                    GEMINI_MODELS
                ) - 1:

                    time.sleep(2)

                continue

            # ------------------------------------------------
            # 429
            # ------------------------------------------------

            if response.status_code == 429:

                print(
                    "❌ Gemini quota/rate limit."
                )

                print(
                    response.text[:3000]
                )

                return None

            # ------------------------------------------------
            # 400
            # ------------------------------------------------

            if response.status_code == 400:

                print(
                    "❌ Gemini BAD REQUEST."
                )

                print(
                    response.text[:3000]
                )

                return None

            # ------------------------------------------------
            # 401 / 403
            # ------------------------------------------------

            if response.status_code in (
                401,
                403
            ):

                print(
                    "❌ Gemini API KEY / "
                    "PERMISSION ERROR."
                )

                print(
                    response.text[:3000]
                )

                return None

            # ------------------------------------------------
            # OTHER
            # ------------------------------------------------

            print(
                "⚠️ Gemini API error:"
            )

            print(
                response.text[:3000]
            )

            continue

        except requests.exceptions.Timeout:

            print(
                "⚠️ Gemini request timed out."
            )

            continue

        except requests.exceptions.RequestException as error:

            print(
                "❌ Gemini network error:",
                type(error).__name__,
                str(error)
            )

            continue

        except Exception as error:

            print(
                "❌ Gemini unexpected error:",
                type(error).__name__,
                str(error)
            )

            continue

    print()
    print("========================================")
    print("❌ ALL GEMINI MODELS FAILED")
    print("========================================")
    print()

    return None


# ============================================================
# FULL REPOSITORY ANALYSIS
# ============================================================

def analyze_repository(
    repository,
    files
):

    context = build_repository_context(
        repository,
        files
    )

    prompt = f"""
You are Gitora AI, an expert software engineer
and repository analyst.

Analyze the supplied GitHub repository using ONLY
the repository information and source code supplied below.

Do not invent technologies, APIs, databases,
authentication systems, routes, dependencies,
or behavior.

If something cannot be identified, return:

"None identified."

REPOSITORY:

{context}

Return ONLY valid JSON.

Use exactly this structure:

{{
  "project_summary": "Explain what the project does.",

  "technology_stack": [
    "Technology and its actual purpose"
  ],

  "architecture": "Explain how the major parts connect.",

  "dependencies": [
    "Important dependency and why it is used"
  ],

  "database": "Explain database usage, models, tables, or say None identified.",

  "authentication": "Explain authentication/login/session handling or say None identified.",

  "important_requests": [
    "Actual API request, route, endpoint, database operation, or external service call"
  ],

  "routing": [
    "Important route and what it does"
  ],

  "run_instructions": [
    "Concrete steps required to run the project"
  ],

  "estimated_development_time": "Estimate based on supplied project complexity.",

  "folder_structure": "Explain important project folders/files and their responsibilities.",

  "file_analysis": [
    {{
      "file": "Exact file path",
      "what_it_does": "What this file actually does.",
      "why_it_exists": "Why this file exists.",
      "website_role": "How this file helps the website/application.",
      "dependencies": [
        "Actual dependencies"
      ],
      "important_requests": [
        "Actual requests, routes, APIs, database operations, or external calls"
      ],
      "what_breaks": "What specifically breaks if this file is removed."
    }}
  ],

  "rebuild_options": [
    {{
      "title": "Alternative implementation",
      "description": "Explain the alternative.",
      "technology": [
        "Suggested technologies"
      ],
      "estimated_time": "Estimated development time"
    }}
  ]
}}

For EVERY supplied file explain:

1. What it does.
2. Why it exists.
3. How it helps the website.
4. What it depends on.
5. Important requests/routes/APIs/database operations.
6. What breaks if it is removed.

Return JSON only.
"""

    data = call_gemini_json(
        prompt
    )

    if data is None:

        return empty_analysis(
            "Gemini could not generate repository analysis."
        )

    return normalize_analysis(
        data
    )


# ============================================================
# INDIVIDUAL FILE ANALYSIS
# ============================================================

def analyze_single_file(
    repository,
    files,
    selected_file
):

    if not selected_file:

        return empty_file_analysis(
            message="No file was selected."
        )

    selected_file = str(
        selected_file
    ).strip()

    selected_content = None

    for file in files or []:

        if not isinstance(file, dict):
            continue

        path = str(
            file.get("path", "")
        ).strip()

        if path == selected_file:

            selected_content = file.get(
                "content",
                ""
            )

            break

    if selected_content is None:

        return empty_file_analysis(
            file_path=selected_file,
            message=(
                "Selected file was not found "
                "in the supplied repository."
            )
        )

    selected_content = str(
        selected_content
    )

    if len(selected_content) > 50000:

        selected_content = (
            selected_content[:50000]
            + "\n\n[FILE CONTENT TRUNCATED]"
        )

    repository_files = []

    for file in files or []:

        if not isinstance(file, dict):
            continue

        path = safe_value(
            file.get("path"),
            ""
        )

        if path:
            repository_files.append(path)

    repository_name = safe_value(
        (repository or {}).get("name"),
        "Unknown repository"
    )

    prompt = f"""
You are Gitora AI, an expert software engineer.

Analyze ONE specific file from this GitHub project.

Repository:
{repository_name}

All repository files:
{json.dumps(
    repository_files,
    ensure_ascii=False,
    indent=2
)}

Selected file:
{selected_file}

Selected file source code:

--------------------------------------------------
{selected_content}
--------------------------------------------------

Use ONLY the supplied source code and repository file names.

Return ONLY valid JSON:

{{
  "file": "{selected_file}",

  "what_it_does": "Explain exactly what this file does.",

  "why_it_exists": "Explain why this file is needed.",

  "website_role": "Explain concretely how this file helps the website or application.",

  "dependencies": [
    "Actual files, modules, libraries, services, APIs, models, or components"
  ],

  "important_requests": [
    "Actual API requests, routes, endpoints, database operations, or external calls"
  ],

  "what_breaks": "Explain exactly what stops working if this file is removed."
}}

Do not invent information.

If something cannot be identified:

"None identified."

Return JSON only.
"""

    data = call_gemini_json(
        prompt
    )

    if data is None:

        return empty_file_analysis(
            file_path=selected_file,
            message=(
                "Gemini could not analyze this file."
            )
        )

    if not isinstance(data, dict):

        return empty_file_analysis(
            file_path=selected_file,
            message=(
                "Gemini returned an invalid "
                "file analysis."
            )
        )

    data["file"] = selected_file

    return normalize_file_analysis(
        data
    )


# ============================================================
# ASK AI
# ============================================================

def answer_repository_question(
    question,
    repository,
    files
):

    question = safe_value(
        question,
        ""
    )

    if not question:
        return "Please enter a question."

    context = build_repository_context(
        repository,
        files
    )

    prompt = f"""
You are Gitora AI, an expert software engineer.

Answer the user's question about the supplied GitHub repository.

Use ONLY the supplied repository information and source code.

Do not invent information.

Repository:

{context}

User question:

{question}

Give a clear practical answer.

When useful, mention:
- exact files
- functions
- classes
- routes
- APIs
- database models
- dependencies
- frontend/backend connections

Return normal human-readable text.
"""

    if not GEMINI_API_KEY:

        return (
            "Gemini API key is not configured. "
            "Please add GEMINI_API_KEY to the "
            "Render environment variables."
        )

    payload = {

        "contents": [
            {
                "parts": [
                    {
                        "text": prompt
                    }
                ]
            }
        ],

        "generationConfig": {
            "temperature": 0.3
        }
    }

    headers = {

        "Content-Type":
            "application/json",

        "x-goog-api-key":
            GEMINI_API_KEY
    }

    for index, model_name in enumerate(
        GEMINI_MODELS
    ):

        print()
        print("----------------------------------------")
        print("🔥 GEMINI QUESTION")
        print("----------------------------------------")
        print(
            "Model:",
            model_name
        )

        try:

            response = requests.post(

                get_gemini_url(
                    model_name
                ),

                headers=headers,

                json=payload,

                timeout=120
            )

            print(
                "Gemini question status:",
                response.status_code
            )

            if response.status_code == 200:

                response_data = (
                    response.json()
                )

                candidates = (
                    response_data.get(
                        "candidates",
                        []
                    )
                )

                if not candidates:
                    continue

                parts = (
                    candidates[0]
                    .get(
                        "content",
                        {}
                    )
                    .get(
                        "parts",
                        []
                    )
                )

                if not parts:
                    continue

                answer = str(
                    parts[0].get(
                        "text",
                        ""
                    )
                ).strip()

                if answer:

                    print(
                        "✅ GEMINI QUESTION SUCCESS"
                    )

                    return answer

                continue

            if response.status_code == 503:

                time.sleep(2)
                continue

            if response.status_code == 429:

                return (
                    "Gemini quota/rate limit reached. "
                    "Please try again later."
                )

            if response.status_code in (
                400,
                401,
                403
            ):

                print(
                    response.text[:3000]
                )

                return (
                    "Gemini API configuration error. "
                    "Please check GEMINI_API_KEY "
                    "and GEMINI_MODEL in Render."
                )

            print(
                response.text[:2000]
            )

        except requests.exceptions.Timeout:

            print(
                "⚠️ Gemini question timed out."
            )

        except requests.exceptions.RequestException as error:

            print(
                "❌ Gemini question network error:",
                type(error).__name__,
                str(error)
            )

        except Exception as error:

            print(
                "❌ Gemini question error:",
                type(error).__name__,
                str(error)
            )

    return (
        "Gemini could not answer the question right now. "
        "Please try again."
    )


# ============================================================
# REBUILD STRATEGIES
# ============================================================

def generate_rebuild_strategies(
    repository,
    files
):

    context = build_repository_context(
        repository,
        files
    )

    prompt = f"""
You are Gitora AI, an expert software architect.

Analyze the supplied project and suggest THREE
realistic ways to rebuild it.

Use ONLY information supported by the supplied project.

Repository:

{context}

Return ONLY valid JSON:

{{
  "rebuild_options": [
    {{
      "title": "Approach name",
      "description": "Explain the approach.",
      "technology": [
        "Technology 1",
        "Technology 2"
      ],
      "estimated_time": "Estimated development time"
    }}
  ]
}}

Make the three approaches meaningfully different.

Return JSON only.
"""

    data = call_gemini_json(
        prompt
    )

    if data is None:
        return []

    if isinstance(data, dict):

        options = (
            data.get("rebuild_options")
            or data.get("rebuild_ways")
            or data.get("ways")
            or []
        )

    elif isinstance(data, list):

        options = data

    else:

        return []

    if not isinstance(options, list):
        return []

    result = []

    for item in options:

        if not isinstance(item, dict):
            continue

        result.append({

            "title": safe_value(
                item.get("title")
                or item.get("name")
                or item.get("approach")
            ),

            "description": safe_value(
                item.get("description")
                or item.get("details")
            ),

            "technology": normalize_list(
                item.get("technology")
                or item.get("technologies")
                or item.get("stack")
            ),

            "estimated_time": safe_value(
                item.get("estimated_time")
                or item.get("time")
            )
        })

    return result