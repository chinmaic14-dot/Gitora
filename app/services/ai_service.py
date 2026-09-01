# app/services/ai_service.py

import json
import re
import os

from openai import OpenAI


# =====================================================
# OPENAI CONFIGURATION
# =====================================================

MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4o-mini"
)

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY"
)

client = (
    OpenAI(api_key=OPENAI_API_KEY)
    if OPENAI_API_KEY
    else None
)

NIL = "None identified."


# =====================================================
# SAFE VALUE
# =====================================================

def safe_value(value, default=NIL):

    if value is None:
        return default

    if isinstance(value, str):

        value = value.strip()

        return value if value else default

    if isinstance(value, list):

        if not value:
            return []

        return value

    if isinstance(value, dict):

        if not value:
            return {}

        return value

    return str(value)


# =====================================================
# NORMALIZE LIST
# =====================================================

def normalize_list(value):

    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):

        value = value.strip()

        if not value:
            return []

        return [value]

    return [str(value)]


# =====================================================
# BUILD REPOSITORY CONTEXT
# =====================================================

def build_repository_context(repository, files):

    context = []

    context.append(
        f"Repository: {repository.get('full_name', '')}"
    )

    context.append(
        f"Repository name: {repository.get('name', '')}"
    )

    context.append(
        f"Default branch: "
        f"{repository.get('default_branch', '')}"
    )

    context.append(
        """
IMPORTANT ANALYSIS RULES:

The following is the ACTUAL source code supplied
from the repository.

Analyze ONLY this supplied source code.

DO NOT invent:

- frameworks
- libraries
- APIs
- databases
- authentication
- commands
- environment variables
- features
- routes
- files
- deployment systems

If something cannot be determined from the supplied
source code, explicitly say:

"None identified."

For setup/run instructions, only provide commands
that can reasonably be determined from visible files.
"""
    )

    for file in files:

        path = file.get("path", "")

        content = file.get("content", "")

        if content is None:
            content = ""

        content = str(content)

        if len(content) > 30000:

            content = (
                content[:30000]
                + "\n\n[GITORA AI: FILE TRUNCATED]\n"
            )

        context.append(
            f"\n===== FILE: {path} =====\n"
        )

        context.append(content)

    return "\n".join(context)


# =====================================================
# EMPTY FULL ANALYSIS
# =====================================================

def empty_analysis(message="No analysis available."):

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

        "estimated_development_time": message,

        "run_instructions": [],

        "folder_structure": message
    }


# =====================================================
# EMPTY FILE ANALYSIS
# =====================================================

def empty_file_analysis(
    file_path,
    message="No analysis available."
):

    return {

        "file": file_path,

        "what_it_does": message,

        "why_it_exists": message,

        "website_role": message,

        "dependencies": [],

        "important_requests": [],

        "what_breaks": message
    }


# =====================================================
# EXTRACT JSON
# =====================================================

def extract_json(text):

    if not text:
        return None

    text = text.strip()

    # -------------------------------------------------
    # DIRECT JSON
    # -------------------------------------------------

    try:

        return json.loads(text)

    except Exception:
        pass

    # -------------------------------------------------
    # REMOVE MARKDOWN CODE BLOCK
    # -------------------------------------------------

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

    # -------------------------------------------------
    # FIND JSON OBJECT INSIDE RESPONSE
    # -------------------------------------------------

    start = text.find("{")

    if start == -1:
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(
        start,
        len(text)
    ):

        char = text[index]

        if escaped:

            escaped = False

            continue

        if char == "\\" and in_string:

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

                    return json.loads(
                        candidate
                    )

                except Exception:

                    return None

    return None


# =====================================================
# NORMALIZE FULL ANALYSIS
# =====================================================

def normalize_analysis(result):

    if not isinstance(result, dict):

        return empty_analysis(
            "Gitora AI returned an invalid analysis."
        )

    result["project_summary"] = safe_value(
        result.get(
            "project_summary",
            NIL
        )
    )

    result["architecture"] = safe_value(
        result.get(
            "architecture",
            NIL
        )
    )

    result["database"] = safe_value(
        result.get(
            "database",
            NIL
        )
    )

    result["authentication"] = safe_value(
        result.get(
            "authentication",
            NIL
        )
    )

    result["folder_structure"] = safe_value(
        result.get(
            "folder_structure",
            NIL
        )
    )

    result["estimated_development_time"] = safe_value(
        result.get(
            "estimated_development_time",
            NIL
        )
    )

    result["technology_stack"] = normalize_list(
        result.get(
            "technology_stack",
            []
        )
    )

    result["dependencies"] = normalize_list(
        result.get(
            "dependencies",
            []
        )
    )

    result["important_requests"] = normalize_list(
        result.get(
            "important_requests",
            []
        )
    )

    result["project_flow"] = normalize_list(
        result.get(
            "project_flow",
            []
        )
    )

    result["important_files"] = normalize_list(
        result.get(
            "important_files",
            []
        )
    )

    result["failure_points"] = normalize_list(
        result.get(
            "failure_points",
            []
        )
    )

    result["run_instructions"] = normalize_list(
        result.get(
            "run_instructions",
            []
        )
    )

    # -------------------------------------------------
    # FILE ANALYSIS
    # -------------------------------------------------

    if not isinstance(
        result.get("file_analysis"),
        list
    ):

        result["file_analysis"] = []

    normalized_files = []

    for item in result["file_analysis"]:

        if not isinstance(item, dict):
            continue

        normalized_files.append({

            "file":
                safe_value(
                    item.get(
                        "file",
                        ""
                    )
                ),

            "what_it_does":
                safe_value(
                    item.get(
                        "what_it_does",
                        NIL
                    )
                ),

            "why_it_exists":
                safe_value(
                    item.get(
                        "why_it_exists",
                        NIL
                    )
                ),

            "website_role":
                safe_value(
                    item.get(
                        "website_role",
                        NIL
                    )
                ),

            "dependencies":
                normalize_list(
                    item.get(
                        "dependencies",
                        []
                    )
                ),

            "important_requests":
                normalize_list(
                    item.get(
                        "important_requests",
                        []
                    )
                ),

            "what_breaks":
                safe_value(
                    item.get(
                        "what_breaks",
                        NIL
                    )
                )
        })

    result["file_analysis"] = normalized_files

    # -------------------------------------------------
    # REBUILD STRATEGIES
    # -------------------------------------------------

    rebuild_ways = result.get(
        "rebuild_ways"
    )

    if rebuild_ways is None:

        rebuild_ways = result.get(
            "build_approaches",
            []
        )

    if rebuild_ways is None:

        rebuild_ways = result.get(
            "rebuild_options",
            []
        )

    if not isinstance(
        rebuild_ways,
        list
    ):

        rebuild_ways = []

    normalized_rebuild = []

    for item in rebuild_ways:

        if isinstance(item, str):

            normalized_rebuild.append({

                "name": "Rebuild Approach",

                "approach": item,

                "description": item,

                "technologies": [],

                "architecture": "",

                "steps": [],

                "advantages": [],

                "limitations": [],

                "estimated_time": ""
            })

            continue

        if not isinstance(item, dict):
            continue

        normalized_rebuild.append({

            "name":
                safe_value(
                    item.get(
                        "name",
                        "Rebuild Approach"
                    ),
                    "Rebuild Approach"
                ),

            "approach":
                safe_value(
                    item.get(
                        "approach",
                        item.get(
                            "description",
                            NIL
                        )
                    )
                ),

            "description":
                safe_value(
                    item.get(
                        "description",
                        item.get(
                            "approach",
                            NIL
                        )
                    )
                ),

            "technologies":
                normalize_list(
                    item.get(
                        "technologies",
                        []
                    )
                ),

            "architecture":
                safe_value(
                    item.get(
                        "architecture",
                        NIL
                    )
                ),

            "steps":
                normalize_list(
                    item.get(
                        "steps",
                        []
                    )
                ),

            "advantages":
                normalize_list(
                    item.get(
                        "advantages",
                        []
                    )
                ),

            "limitations":
                normalize_list(
                    item.get(
                        "limitations",
                        []
                    )
                ),

            "estimated_time":
                safe_value(
                    item.get(
                        "estimated_time",
                        NIL
                    )
                )
        })

    result["rebuild_ways"] = normalized_rebuild[:3]

    result["build_approaches"] = result[
        "rebuild_ways"
    ]

    return result


# =====================================================
# NORMALIZE SINGLE FILE
# =====================================================

def normalize_file_analysis(
    result,
    file_path
):

    if not isinstance(
        result,
        dict
    ):

        return empty_file_analysis(
            file_path,
            "Gitora AI returned an invalid analysis."
        )

    return {

        "file":
            safe_value(
                result.get(
                    "file",
                    file_path
                ),
                file_path
            ),

        "what_it_does":
            safe_value(
                result.get(
                    "what_it_does",
                    NIL
                )
            ),

        "why_it_exists":
            safe_value(
                result.get(
                    "why_it_exists",
                    NIL
                )
            ),

        "website_role":
            safe_value(
                result.get(
                    "website_role",
                    NIL
                )
            ),

        "dependencies":
            normalize_list(
                result.get(
                    "dependencies",
                    []
                )
            ),

        "important_requests":
            normalize_list(
                result.get(
                    "important_requests",
                    []
                )
            ),

        "what_breaks":
            safe_value(
                result.get(
                    "what_breaks",
                    NIL
                )
            )
    }


# =====================================================
# OPENAI JSON CALL
# =====================================================

def call_openai_json(
    system_prompt,
    user_prompt,
    retry_prompt=None
):

    if client is None:

        print(
            "\n========== GITORA OPENAI ERROR =========="
        )

        print(
            "OPENAI_API_KEY is not configured."
        )

        print(
            "==========================================\n"
        )

        return None

    # -------------------------------------------------
    # FIRST ATTEMPT
    # -------------------------------------------------

    try:

        response = client.chat.completions.create(

            model=MODEL,

            messages=[

                {
                    "role": "system",
                    "content": system_prompt
                },

                {
                    "role": "user",
                    "content": user_prompt
                }

            ],

            response_format={
                "type": "json_object"
            }

        )

        raw = response.choices[
            0
        ].message.content

        print(
            "\n========== GITORA OPENAI RESPONSE =========="
        )

        print(raw)

        print(
            "=============================================\n"
        )

        result = extract_json(raw)

        if result is not None:

            return result

        print(
            "\n========== GITORA JSON PARSE FAILED =========="
        )

        print(raw)

        print(
            "===============================================\n"
        )

    except Exception as error:

        print(
            "\n========== GITORA OPENAI ERROR =========="
        )

        print(error)

        print(
            "==========================================\n"
        )

    # -------------------------------------------------
    # SECOND ATTEMPT
    # -------------------------------------------------

    if retry_prompt:

        try:

            response = client.chat.completions.create(

                model=MODEL,

                messages=[

                    {
                        "role": "system",
                        "content": system_prompt
                    },

                    {
                        "role": "user",
                        "content": retry_prompt
                    }

                ],

                response_format={
                    "type": "json_object"
                }

            )

            raw = response.choices[
                0
            ].message.content

            print(
                "\n========== GITORA RETRY RESPONSE =========="
            )

            print(raw)

            print(
                "===========================================\n"
            )

            result = extract_json(raw)

            if result is not None:

                return result

        except Exception as error:

            print(
                "\n========== GITORA RETRY ERROR =========="
            )

            print(error)

            print(
                "========================================\n"
            )

    return None


# =====================================================
# FULL REPOSITORY ANALYSIS
# =====================================================

def analyze_repository(
    repository,
    files
):

    if not files:

        return empty_analysis(
            "No files have been selected."
        )

    context = build_repository_context(
        repository,
        files
    )

    system_prompt = """
You are Gitora AI, a professional software
repository intelligence assistant.

Analyze ONLY the actual source code supplied.

NEVER invent functionality.

NEVER assume something exists unless visible
in the supplied files.

Your response MUST contain ONLY valid JSON.

=================================================
EXACT JSON STRUCTURE
=================================================

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

=================================================
PROJECT SUMMARY
=================================================

project_summary:

Clearly explain what the actual project does.

Only describe functionality visible in the source.

=================================================
TECHNOLOGY STACK
=================================================

technology_stack:

List actual:

- programming languages
- frameworks
- libraries
- tools
- platforms

Only if visible in source files.

=================================================
ARCHITECTURE
=================================================

architecture:

Explain how the actual components communicate.

Only describe connections visible in code.

=================================================
DEPENDENCIES
=================================================

dependencies:

Identify actual dependencies from:

- imports
- requirements files
- package files
- configuration files

Do not invent packages.

=================================================
DATABASE
=================================================

database:

Explain:

- database technology
- models
- tables
- schemas
- ORM
- database connection

Only if visible.

If absent:

"None identified."

=================================================
AUTHENTICATION
=================================================

authentication:

Identify actual:

- login
- signup
- sessions
- JWT
- OAuth
- tokens
- password handling

If absent:

"None identified."

=================================================
IMPORTANT API REQUESTS
=================================================

important_requests:

Only identify actual network/API requests.

Each object:

{
  "api": "",
  "file": "",
  "purpose": "",
  "usage": ""
}

Do not invent API endpoints.

=================================================
FILE ANALYSIS
=================================================

Create ONE object for EVERY supplied source file.

Structure:

{
  "file": "",
  "what_it_does": "",
  "why_it_exists": "",
  "website_role": "",
  "dependencies": [],
  "important_requests": [],
  "what_breaks": ""
}

Do not skip supplied files.

=================================================
PROJECT FLOW
=================================================

project_flow:

Explain the ACTUAL execution flow step-by-step.

Only include steps supported by source code.

=================================================
IMPORTANT FILES
=================================================

important_files:

Identify the most important files.

Each object:

{
  "file": "",
  "importance": "",
  "reason": ""
}

=================================================
FAILURE POINTS
=================================================

failure_points:

Identify realistic problems visible from the source.

Each object:

{
  "area": "",
  "risk": "",
  "reason": "",
  "affected_files": []
}

Do not invent vulnerabilities.

=================================================
3 WAYS TO REBUILD
=================================================

rebuild_ways:

Generate exactly THREE meaningful alternatives
for rebuilding the SAME project.

Approach 1:
Beginner / Simple

Approach 2:
Modern / Production

Approach 3:
Scalable / Advanced

Each object:

{
  "name": "",
  "approach": "",
  "description": "",
  "technologies": [],
  "architecture": "",
  "steps": [],
  "advantages": [],
  "limitations": [],
  "estimated_time": ""
}

Clearly separate alternatives from the existing project.

=================================================
ESTIMATED DEVELOPMENT TIME
=================================================

estimated_development_time:

Give a realistic rough estimate for rebuilding
a similar project from scratch.

=================================================
RUN / SETUP INSTRUCTIONS
=================================================

run_instructions:

Automatically determine how the supplied project
can be installed and started.

Look for actual evidence such as:

- requirements.txt
- package.json
- package-lock.json
- pyproject.toml
- Pipfile
- Dockerfile
- docker-compose.yml
- .env examples
- Flask app
- Django manage.py
- Node scripts
- Python entry points
- README instructions

Return practical steps.

Only provide commands that can be determined
from the supplied files.

Do NOT invent commands.

For environment variables, only mention variables
actually visible in the source.

NEVER expose actual secret values.

=================================================
FOLDER STRUCTURE
=================================================

folder_structure:

Describe the actual visible file/folder structure.

Do not invent missing folders.

=================================================
FINAL RULE
=================================================

If information is unavailable:

Use:

"None identified."

or:

"Could not be determined from supplied files."

Return ONLY JSON.
"""

    user_prompt = f"""
Analyze this repository.

Repository:
{repository.get('full_name', '')}

SOURCE CODE:

{context}
"""

    retry_prompt = f"""
The previous response was invalid or incomplete.

Return ONLY valid JSON.

No Markdown.
No Python.
No explanation.

Analyze ONLY this supplied repository source.

{context}

The JSON MUST contain exactly these major fields:

{{
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
}}

IMPORTANT:

The file_analysis array MUST contain one entry
for EVERY supplied file.

The rebuild_ways array MUST contain exactly
THREE strategies.

run_instructions MUST contain actual setup/run
instructions only when they can be determined
from the supplied files.

Do not invent commands.
"""

    result = call_openai_json(

        system_prompt=system_prompt,

        user_prompt=user_prompt,

        retry_prompt=retry_prompt
    )

    if result is None:

        return empty_analysis(
            "Gitora AI could not produce a valid "
            "structured analysis."
        )

    return normalize_analysis(
        result
    )


# =====================================================
# INDIVIDUAL FILE ANALYSIS
# =====================================================

def analyze_single_file(
    repository,
    file_path,
    content,
    all_files=None
):

    if not content:

        return empty_file_analysis(
            file_path,
            "No source code was available."
        )

    context = ""

    if all_files:

        for file in all_files:

            other_path = file.get(
                "path",
                ""
            )

            other_content = file.get(
                "content",
                ""
            )

            if other_content is None:

                other_content = ""

            other_content = str(
                other_content
            )

            if len(other_content) > 12000:

                other_content = (
                    other_content[:12000]
                    + "\n[TRUNCATED]"
                )

            context += (
                f"\n===== {other_path} =====\n"
            )

            context += other_content

    system_prompt = """
You are Gitora AI.

Analyze ONE actual source file.

Use ONLY supplied source code.

Do not invent functionality.

Return ONLY valid JSON.

Use exactly:

{
  "file": "",
  "what_it_does": "",
  "why_it_exists": "",
  "website_role": "",
  "dependencies": [],
  "important_requests": [],
  "what_breaks": ""
}

Explain:

1. What the file does.
2. Why the file exists.
3. How it contributes to the website/project.
4. What libraries/files it depends on.
5. What external API requests it makes.
6. What would break if it were removed.

If there are no API requests:

"important_requests": []

If something cannot be determined:

"None identified."

Return ONLY JSON.
"""

    user_prompt = f"""
Repository:
{repository.get('full_name', '')}

TARGET FILE:
{file_path}

SOURCE CODE:

{content}

OTHER SELECTED FILES FOR CONTEXT:

{context}
"""

    retry_prompt = f"""
Return ONLY valid JSON.

No Markdown.
No Python.
No explanation.

{{
  "file": "{file_path}",
  "what_it_does": "",
  "why_it_exists": "",
  "website_role": "",
  "dependencies": [],
  "important_requests": [],
  "what_breaks": ""
}}

Analyze ONLY this actual file:

{content}
"""

    result = call_openai_json(

        system_prompt=system_prompt,

        user_prompt=user_prompt,

        retry_prompt=retry_prompt
    )

    if result is None:

        return empty_file_analysis(
            file_path,
            "Gitora AI could not produce a valid "
            "structured analysis."
        )

    return normalize_file_analysis(
        result,
        file_path
    )


# =====================================================
# ASK GITORA AI
# =====================================================

def answer_repository_question(
    question,
    repository,
    files
):

    if not files:

        return (
            "No files have been selected. "
            "Please select and save repository files first."
        )

    if client is None:

        return (
            "Gitora AI is not configured. "
            "Please configure OPENAI_API_KEY."
        )

    context = build_repository_context(
        repository,
        files
    )

    system_prompt = """
You are Gitora AI.

Answer questions about the ACTUAL repository
source code supplied by the user.

Rules:

1. Use only supplied source code.
2. Do not invent functionality.
3. Mention exact filenames when useful.
4. Explain concepts clearly.
5. Explain API requests when relevant.
6. Explain setup/run behavior when relevant.
7. If information cannot be determined,
   explicitly say so.
8. Focus on the actual repository.

Return a normal helpful answer.

Do NOT pretend that something exists if it is
not visible in the supplied code.
"""

    user_prompt = f"""
Repository:
{repository.get('full_name', '')}

SOURCE CODE:

{context}

USER QUESTION:

{question}
"""

    try:

        response = client.chat.completions.create(

            model=MODEL,

            messages=[

                {
                    "role": "system",
                    "content": system_prompt
                },

                {
                    "role": "user",
                    "content": user_prompt
                }

            ]

        )

        return response.choices[
            0
        ].message.content.strip()

    except Exception as error:

        print(
            "\n========== GITORA CHAT ERROR =========="
        )

        print(error)

        print(
            "=======================================\n"
        )

        return (
            "Gitora AI could not connect to OpenAI. "
            "Check the OPENAI_API_KEY and try again."
        )


# =====================================================
# THREE WAYS TO REBUILD PROJECT
# =====================================================

def generate_rebuild_strategies(
    repository,
    files
):

    if not files:
        return []

    if client is None:
        return []

    context = build_repository_context(
        repository,
        files
    )

    system_prompt = """
You are Gitora AI.

Analyze ONLY the supplied repository source.

Generate exactly THREE realistic ways to rebuild
the same project.

The three approaches MUST be:

1. Beginner / Simple
2. Modern / Production
3. Scalable / Advanced

These are alternative architectures.

Do not claim that these alternatives are the
existing implementation.

Return ONLY valid JSON.

Structure:

{
  "rebuild_strategies": [
    {
      "name": "",
      "approach": "",
      "description": "",
      "technologies": [],
      "architecture": "",
      "steps": [],
      "advantages": [],
      "limitations": [],
      "estimated_time": ""
    }
  ]
}

There MUST be exactly three objects.
"""

    user_prompt = f"""
Repository:
{repository.get('full_name', '')}

SOURCE CODE:

{context}

Generate exactly three practical rebuild strategies.
"""

    retry_prompt = f"""
Return ONLY valid JSON.

No Markdown.
No Python.
No explanation.

{{
  "rebuild_strategies": [
    {{
      "name": "",
      "approach": "",
      "description": "",
      "technologies": [],
      "architecture": "",
      "steps": [],
      "advantages": [],
      "limitations": [],
      "estimated_time": ""
    }},
    {{
      "name": "",
      "approach": "",
      "description": "",
      "technologies": [],
      "architecture": "",
      "steps": [],
      "advantages": [],
      "limitations": [],
      "estimated_time": ""
    }},
    {{
      "name": "",
      "approach": "",
      "description": "",
      "technologies": [],
      "architecture": "",
      "steps": [],
      "advantages": [],
      "limitations": [],
      "estimated_time": ""
    }}
  ]
}}

Analyze ONLY:

{context}
"""

    result = call_openai_json(

        system_prompt=system_prompt,

        user_prompt=user_prompt,

        retry_prompt=retry_prompt
    )

    if not isinstance(
        result,
        dict
    ):

        return []

    strategies = result.get(
        "rebuild_strategies",
        []
    )

    if not isinstance(
        strategies,
        list
    ):

        return []

    normalized = []

    for item in strategies:

        if not isinstance(
            item,
            dict
        ):
            continue

        normalized.append({

            "name":
                safe_value(
                    item.get(
                        "name",
                        "Rebuild Approach"
                    )
                ),

            "approach":
                safe_value(
                    item.get(
                        "approach",
                        NIL
                    )
                ),

            "description":
                safe_value(
                    item.get(
                        "description",
                        item.get(
                            "approach",
                            NIL
                        )
                    )
                ),

            "technologies":
                normalize_list(
                    item.get(
                        "technologies",
                        []
                    )
                ),

            "architecture":
                safe_value(
                    item.get(
                        "architecture",
                        NIL
                    )
                ),

            "steps":
                normalize_list(
                    item.get(
                        "steps",
                        []
                    )
                ),

            "advantages":
                normalize_list(
                    item.get(
                        "advantages",
                        []
                    )
                ),

            "limitations":
                normalize_list(
                    item.get(
                        "limitations",
                        []
                    )
                ),

            "estimated_time":
                safe_value(
                    item.get(
                        "estimated_time",
                        NIL
                    )
                )
        })

    return normalized[:3]