# =====================================================
# GITORA AI - ARCHITECTURE SERVICE
# =====================================================

def detect_architecture(files):
    """
    Detect the major components of a repository
    using the actual file paths.

    No AI assumptions are made here.
    """

    architecture = {
        "entry_points": [],
        "frontend": [],
        "routes": [],
        "services": [],
        "database": [],
        "authentication": [],
        "external_apis": [],
        "other": []
    }

    for file in files:

        path = file.get("path", "")

        if not path:
            continue

        lower_path = path.lower()

        # -------------------------------------------------
        # ENTRY POINTS
        # -------------------------------------------------

        if lower_path.endswith(
            (
                "app.py",
                "main.py",
                "run.py",
                "server.py",
                "index.js",
                "server.js"
            )
        ):

            architecture["entry_points"].append(path)

        # -------------------------------------------------
        # FRONTEND
        # -------------------------------------------------

        if lower_path.endswith(
            (
                ".html",
                ".css",
                ".scss",
                ".jsx",
                ".tsx"
            )
        ):

            architecture["frontend"].append(path)

        # -------------------------------------------------
        # ROUTES / API
        # -------------------------------------------------

        if any(
            keyword in lower_path
            for keyword in [
                "route",
                "routes",
                "controller",
                "api",
                "views"
            ]
        ):

            architecture["routes"].append(path)

        # -------------------------------------------------
        # SERVICES
        # -------------------------------------------------

        if (
            "/services/" in lower_path
            or "\\services\\" in lower_path
            or lower_path.startswith("services/")
            or lower_path.startswith("services\\")
        ):

            architecture["services"].append(path)

        # -------------------------------------------------
        # DATABASE
        # -------------------------------------------------

        if any(
            keyword in lower_path
            for keyword in [
                "model",
                "models",
                "database",
                "db",
                "schema"
            ]
        ):

            architecture["database"].append(path)

        # -------------------------------------------------
        # AUTHENTICATION
        # -------------------------------------------------

        if any(
            keyword in lower_path
            for keyword in [
                "auth",
                "login",
                "register",
                "signup"
            ]
        ):

            architecture["authentication"].append(path)

        # -------------------------------------------------
        # OTHER
        # -------------------------------------------------

        if not any(
            path in category
            for category in architecture.values()
        ):

            architecture["other"].append(path)

    return architecture


# =====================================================
# BUILD BASIC PROJECT FLOW
# =====================================================

def build_project_flow(architecture):
    """
    Build a simple architecture flow from detected
    repository components.
    """

    flow = []

    if architecture["entry_points"]:

        flow.append({
            "layer": "Entry Point",
            "files": architecture["entry_points"]
        })

    if architecture["frontend"]:

        flow.append({
            "layer": "Frontend",
            "files": architecture["frontend"]
        })

    if architecture["routes"]:

        flow.append({
            "layer": "Routes / API",
            "files": architecture["routes"]
        })

    if architecture["services"]:

        flow.append({
            "layer": "Services",
            "files": architecture["services"]
        })

    if architecture["database"]:

        flow.append({
            "layer": "Database",
            "files": architecture["database"]
        })

    if architecture["external_apis"]:

        flow.append({
            "layer": "External APIs",
            "files": architecture["external_apis"]
        })

    return flow


# =====================================================
# COMPLETE ARCHITECTURE ANALYSIS
# =====================================================

def analyze_architecture(files):
    """
    Main function used by Gitora routes.
    """

    architecture = detect_architecture(files)

    flow = build_project_flow(
        architecture
    )

    return {
        "architecture": architecture,
        "flow": flow
    }