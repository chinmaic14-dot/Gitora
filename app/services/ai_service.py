import os
import json
import re

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# GEMINI CONFIGURATION
# ============================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.6-flash"
)

GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{MODEL}:generateContent"
)


# ============================================================
# SAFE HELPERS
# ============================================================

def safe_value(value, default="None identified."):
    """
    Safely convert a value into a usable string.
    """

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
                values.append(
                    json.dumps(item, ensure_ascii=False)
                )
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

    return str(value).strip() or default


def normalize_list(value):
    """
    Convert Gemini output into a clean list of strings.
    """

    if value is None:
        return []

    if isinstance(value, list):
        result = []

        for item in value:

            if isinstance(item, dict):
                text = safe_value(item, "")
            else:
                text = str(item).strip()

            if text:
                result.append(text)

        return result

    if isinstance(value, dict):
        result = []

        for key, item in value.items():
            text = f"{key}: {safe_value(item, '')}".strip()

            if text:
                result.append(text)

        return result

    if isinstance(value, str):

        value = value.strip()

        if not value:
            return []

        # Handle JSON list returned as string
        try:
            parsed = json.loads(value)

            if isinstance(parsed, list):
                return normalize_list(parsed)
        except Exception:
            pass

        # Handle common separators
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
    """
    Build a compact repository context for Gemini.
    """

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

        content = file.get("content", "")

        if content is None:
            content = ""

        content = str(content)

        # Keep prompts from becoming unnecessarily huge
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
# EMPTY RESPONSES
# ============================================================

def empty_analysis(message="AI analysis unavailable."):
    """
    Standard fallback for repository analysis.
    """

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
        "estimated_development_time": "Not identified.",
        "routing": [],
        "run_instructions": [],
        "folder_structure": message
    }


def empty_file_analysis(
    file_path="",
    message="AI analysis unavailable."
):
    """
    Standard fallback for individual file analysis.
    """

    return {
        "file": file_path,

        "what_it_does": message,

        "why_it_exists": message,

        "website_role": message,

        "dependencies": [],

        "important_requests": [],

        "what_breaks": message,

        # Compatibility fields
        "what_breaks_without_it": message,

        "connections": [],

        "important_code": []
    }


# ============================================================
# JSON EXTRACTION
# ============================================================

def extract_json(text):
    """
    Extract JSON safely from Gemini response.

    Gemini may return:
    - pure JSON
    - JSON inside ```json blocks
    - JSON surrounded by explanation text
    """

    if not text:
        return None

    if not isinstance(text, str):
        text = str(text)

    text = text.strip()

    if not text:
        return None

    # Remove markdown code fences
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

    # Direct JSON
    try:
        return json.loads(text)
    except Exception:
        pass

    # Find JSON object
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

    # Find JSON array
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
# NORMALIZE OVERALL ANALYSIS
# ============================================================

def normalize_analysis(data):
    """
    Normalize Gemini's repository-level response.
    """

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

    file_analysis = data.get("file_analysis")

    if not isinstance(file_analysis, list):
        file_analysis = []

    normalized_files = []

    for item in file_analysis:

        if not isinstance(item, dict):
            continue

        normalized_files.append(
            normalize_file_analysis(item)
        )

    result["file_analysis"] = normalized_files

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
                "description": "None identified.",
                "technology": [],
                "estimated_time": "Not identified."
            })

    result["rebuild_options"] = normalized_rebuild

    return result


# ============================================================
# NORMALIZE INDIVIDUAL FILE ANALYSIS
# ============================================================

def normalize_file_analysis(data):
    """
    Normalize Gemini's individual-file response.

    Canonical fields expected by analysis.html:

    - file
    - what_it_does
    - why_it_exists
    - website_role
    - dependencies
    - important_requests
    - what_breaks
    """

    if not isinstance(data, dict):
        return empty_file_analysis(
            message="Gemini returned an invalid file analysis format."
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

    # --------------------------------------------------------
    # Compatibility aliases
    # --------------------------------------------------------

    result["what_breaks_without_it"] = result[
        "what_breaks"
    ]

    result["connections"] = result[
        "important_requests"
    ]

    result["important_code"] = normalize_list(
        data.get("important_code")
        or data.get("key_code")
        or []
    )

    return result


# ============================================================
# GEMINI API CALL
# ============================================================

def call_gemini_json(prompt):
    """
    Send a prompt to Gemini and return parsed JSON.

    Returns None if the API call fails.
    """

    if not GEMINI_API_KEY:
        print(
            "GEMINI_API_KEY is missing."
        )
        return None

    try:

        import requests

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
                "responseMimeType": "application/json"
            }
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        }

        response = requests.post(
            GEMINI_URL,
            headers=headers,
            json=payload,
            timeout=120
        )

        print(
            "Gemini status:",
            response.status_code
        )

        if response.status_code != 200:
            print(
                "Gemini API error:",
                response.text[:2000]
            )
            return None

        try:
            response_data = response.json()
        except Exception:
            print(
                "Gemini returned invalid HTTP JSON."
            )
            return None

        candidates = response_data.get(
            "candidates",
            []
        )

        if not candidates:
            print(
                "Gemini response contains no candidates."
            )
            return None

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
                "Gemini response contains no parts."
            )
            return None

        text = parts[0].get(
            "text",
            ""
        )

        if not text:
            print(
                "Gemini response text is empty."
            )
            return None

        parsed = extract_json(text)

        if parsed is None:
            print(
                "Could not extract JSON from Gemini response."
            )
            print(
                "Gemini text:",
                text[:3000]
            )
            return None

        return parsed

    except Exception as e:

        print(
            "Gemini API exception:",
            type(e).__name__,
            str(e)
        )

        return None


# ============================================================
# REPOSITORY ANALYSIS
# ============================================================

def analyze_repository(repository, files):
    """
    Analyze the complete GitHub repository.
    """

    context = build_repository_context(
        repository,
        files
    )

    prompt = f"""
You are Gitora AI, an expert software engineer and repository analyst.

Analyze the supplied GitHub repository using ONLY the repository
information and source code provided below.

Do not invent technologies, APIs, databases, authentication systems,
routes, dependencies, or behavior that cannot be supported by the
provided source code.

If something cannot be identified from the supplied code, return:

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

  "architecture": "Explain how the major parts of the project connect.",

  "dependencies": [
    "Important dependency and why it is used"
  ],

  "database": "Explain database usage, models, tables, or say None identified.",

  "authentication": "Explain authentication/login/session handling or say None identified.",

  "important_requests": [
    "Important API request, route, endpoint, database operation, or external service call"
  ],

  "routing": [
    "Important route and what it does"
  ],

  "run_instructions": [
    "Concrete steps required to run the project"
  ],

  "estimated_development_time": "Estimate based on the supplied project complexity.",

  "folder_structure": "Explain the important project folders/files and their responsibilities.",

  "file_analysis": [
    {{
      "file": "Exact file path",

      "what_it_does": "What this file actually does.",

      "why_it_exists": "Why this file is needed in the project.",

      "website_role": "Explain exactly how this file helps the website/application and how it contributes to the user-facing functionality.",

      "dependencies": [
        "Files, modules, services, libraries, database models, or other components this file depends on"
      ],

      "important_requests": [
        "Actual API requests, Flask routes, HTTP calls, database operations, external service calls, or important endpoints found in this file"
      ],

      "what_breaks": "Explain specifically what functionality would stop working, become incomplete, or fail if this file were removed."
    }}
  ],

  "rebuild_options": [
    {{
      "title": "Alternative implementation",

      "description": "Explain how the project could be rebuilt differently.",

      "technology": [
        "Suggested technologies"
      ],

      "estimated_time": "Estimated development time"
    }}
  ]
}}

IMPORTANT FOR file_analysis:

For EVERY file, clearly answer:

1. What does this file do?
2. Why does this file exist?
3. How does this file help the website/project?
4. What files/modules/services does it depend on?
5. What important API requests, routes, endpoints, database operations,
   or external calls are present?
6. What specifically breaks if the file is removed?

Do not provide vague statements such as:
"This file is important."

Explain the actual functionality and consequence.

Only analyze files that were supplied.
"""


    data = call_gemini_json(prompt)

    if data is None:
        return empty_analysis(
            "Gemini could not generate repository analysis."
        )

    return normalize_analysis(data)


# ============================================================
# INDIVIDUAL FILE ANALYSIS
# ============================================================

def analyze_single_file(
    repository,
    files,
    selected_file
):
    """
    Analyze one selected file in the context of the
    complete repository.
    """

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
            message="Selected file was not found in the supplied repository."
        )

    if selected_content is None:
        selected_content = ""

    selected_content = str(
        selected_content
    )

    # Limit extremely large files
    if len(selected_content) > 50000:
        selected_content = (
            selected_content[:50000]
            + "\n\n[FILE CONTENT TRUNCATED]"
        )

    # Build repository-level file map
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

Analyze ONE specific file from the GitHub project below.

Repository:
{repository_name}

All repository files:
{json.dumps(repository_files, ensure_ascii=False, indent=2)}

Selected file:
{selected_file}

Selected file source code:
--------------------------------------------------
{selected_content}
--------------------------------------------------

Your analysis MUST be based ONLY on the supplied source code
and repository file names.

Do NOT invent behavior.

If something cannot be identified from the code, say:

"None identified."

Return ONLY valid JSON.

Use EXACTLY this structure:

{{
  "file": "{selected_file}",

  "what_it_does": "Explain exactly what this file does, including its main functions, classes, routes, UI behavior, database behavior, or processing.",

  "why_it_exists": "Explain why this file is needed and what responsibility it has in the project.",

  "website_role": "Explain concretely HOW THIS FILE HELPS THE WEBSITE OR APPLICATION. Describe the actual user-facing or system-level functionality that depends on it.",

  "dependencies": [
    "Actual files, modules, libraries, services, database models, APIs, or components this file depends on"
  ],

  "important_requests": [
    "Actual HTTP/API requests, Flask routes, endpoints, database operations, external service calls, or other important requests found in this file"
  ],

  "what_breaks": "Explain specifically what would stop working, fail, disappear, or become incomplete if this file were removed."
}}

VERY IMPORTANT:

### WHAT IT DOES
Explain the actual implementation.

### WHY IT EXISTS
Explain the architectural responsibility of this file.

### HOW IT HELPS THE WEBSITE
This is NOT the same as "what it does".

Explain how the file contributes to the complete website/application.

For example:
- Does it render a page?
- Does it handle login?
- Does it connect the frontend to the backend?
- Does it store data?
- Does it process GitHub data?
- Does it generate reports?
- Does it provide an API?
- Does it provide styling or JavaScript behavior?

Only state what is supported by the supplied code.

### DEPENDENCIES
Mention actual imports and project components used by the file.

### IMPORTANT REQUESTS
Mention actual:
- HTTP requests
- API calls
- Flask routes
- endpoints
- database queries
- external services
- GitHub API calls
- Gemini API calls
- AJAX/fetch requests

Do NOT invent requests that are not present.

### WHAT BREAKS
Be specific.

Do NOT simply say:
"This file is important."

Explain what functionality would actually stop working if this file disappeared.

If no important requests or dependencies are visible, return:

"None identified."

For list fields, use [] when there are genuinely no items.

Return JSON only.
"""

    data = call_gemini_json(prompt)

    if data is None:
        return empty_file_analysis(
            file_path=selected_file,
            message="Gemini could not analyze this file."
        )

    if not isinstance(data, dict):
        return empty_file_analysis(
            file_path=selected_file,
            message="Gemini returned an invalid file analysis."
        )

    # Make sure the selected filename is retained
    data["file"] = selected_file

    return normalize_file_analysis(data)


# ============================================================
# ASK AI ABOUT REPOSITORY
# ============================================================

def answer_repository_question(
    question,
    repository,
    files
):
    """
    Answer a user's question about the repository.
    """

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

If the answer cannot be determined from the supplied code,
clearly say:

"None identified from the supplied repository."

Repository context:

{context}

User question:

{question}

Give a clear, practical answer.

When useful, mention:
- exact files
- functions
- classes
- routes
- APIs
- database models
- dependencies
- frontend/backend connections

Do not return JSON.
Return a normal human-readable answer.
"""

    if not GEMINI_API_KEY:
        return (
            "Gemini API key is not configured. "
            "Please add GEMINI_API_KEY to the Render environment variables."
        )

    try:

        import requests

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
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        }

        response = requests.post(
            GEMINI_URL,
            headers=headers,
            json=payload,
            timeout=120
        )

        print(
            "Gemini question status:",
            response.status_code
        )

        if response.status_code != 200:

            print(
                "Gemini question error:",
                response.text[:2000]
            )

            return (
                "Gemini could not answer the question right now."
            )

        try:
            response_data = response.json()
        except Exception:

            return (
                "Gemini returned an invalid response."
            )

        candidates = response_data.get(
            "candidates",
            []
        )

        if not candidates:
            return (
                "Gemini returned no answer."
            )

        parts = (
            candidates[0]
            .get("content", {})
            .get("parts", [])
        )

        if not parts:
            return (
                "Gemini returned an empty answer."
            )

        answer = parts[0].get(
            "text",
            ""
        )

        answer = str(
            answer or ""
        ).strip()

        if not answer:
            return (
                "Gemini returned an empty answer."
            )

        return answer

    except Exception as e:

        print(
            "Gemini question exception:",
            type(e).__name__,
            str(e)
        )

        return (
            "An error occurred while asking Gemini."
        )


# ============================================================
# REBUILD STRATEGIES
# ============================================================

def generate_rebuild_strategies(
    repository,
    files
):
    """
    Generate alternative ways to rebuild the project.
    """

    context = build_repository_context(
        repository,
        files
    )

    prompt = f"""
You are Gitora AI, an expert software architect.

Analyze the supplied project and suggest THREE realistic ways
to rebuild it using different technology choices or architectures.

Use ONLY information supported by the supplied project.

Do not invent requirements.

Repository:

{context}

Return ONLY valid JSON in this structure:

{{
  "rebuild_options": [
    {{
      "title": "Approach name",

      "description": "Explain the architecture and implementation approach.",

      "technology": [
        "Technology 1",
        "Technology 2"
      ],

      "estimated_time": "Estimated development time"
    }}
  ]
}}

Make the three approaches meaningfully different.

For example, where appropriate:
1. Keep the existing architecture but improve it.
2. Rebuild using another backend/frontend stack.
3. Rebuild using a modern full-stack or cloud architecture.

Base the suggestions on the actual project.
"""

    data = call_gemini_json(prompt)

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