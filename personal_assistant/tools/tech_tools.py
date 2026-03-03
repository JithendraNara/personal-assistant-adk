"""
Technology and software engineering tools for the tech_agent.

Covers code analysis, debugging, tech recommendations, and streaming setup.
"""

import os
import re
from typing import Optional


def analyze_code(
    code: str,
    language: str = "python",
    focus: str = "all",
) -> dict:
    """
    Analyze a code snippet for issues, style violations, and improvement opportunities.

    Args:
        code: The source code to analyze.
        language: Programming language — 'python', 'javascript', 'typescript',
                  'csharp', 'terraform', 'sql'.
        focus: What to focus on — 'all', 'bugs', 'performance', 'security',
               'style', 'readability'.

    Returns:
        A dict with 'status', 'language', 'line_count', 'findings', and
        'improved_code_hint'.
    """
    if not code or not code.strip():
        return {"status": "error", "message": "No code provided."}

    valid_languages = {"python", "javascript", "typescript", "csharp", "terraform", "sql", "nodejs"}
    lang = language.lower()
    if lang not in valid_languages:
        lang = "python"

    valid_focuses = {"all", "bugs", "performance", "security", "style", "readability"}
    foc = focus.lower() if focus.lower() in valid_focuses else "all"

    lines = code.strip().splitlines()
    line_count = len(lines)

    # Static analysis hints (LLM will do real analysis)
    static_findings = []

    if lang == "python":
        # Check for common Python issues
        if "except:" in code and "except Exception" not in code:
            static_findings.append({
                "type": "bug",
                "severity": "medium",
                "message": "Bare `except:` clause catches all exceptions including SystemExit. Use `except Exception:` or a specific exception type.",
                "line": next((i + 1 for i, l in enumerate(lines) if "except:" in l), None),
            })
        if "print(" in code and line_count > 20:
            static_findings.append({
                "type": "style",
                "severity": "low",
                "message": "Found print() statements — consider using logging module for production code.",
                "line": next((i + 1 for i, l in enumerate(lines) if "print(" in l), None),
            })
        if "import *" in code:
            static_findings.append({
                "type": "style",
                "severity": "medium",
                "message": "Wildcard imports (`import *`) pollute the namespace. Import explicitly.",
                "line": next((i + 1 for i, l in enumerate(lines) if "import *" in l), None),
            })
        if re.search(r"password\s*=\s*['\"][^'\"]+['\"]", code, re.IGNORECASE):
            static_findings.append({
                "type": "security",
                "severity": "high",
                "message": "Hardcoded password detected. Use environment variables or a secrets manager.",
                "line": None,
            })
        if not any("def " in l for l in lines) and line_count > 30:
            static_findings.append({
                "type": "readability",
                "severity": "low",
                "message": "No functions found in a >30-line file. Consider breaking into functions.",
            })

    elif lang in ("javascript", "typescript", "nodejs"):
        if "var " in code:
            static_findings.append({
                "type": "style",
                "severity": "low",
                "message": "Use `const` or `let` instead of `var` in modern JS/TS.",
                "line": next((i + 1 for i, l in enumerate(lines) if "var " in l), None),
            })
        if "console.log(" in code and line_count > 15:
            static_findings.append({
                "type": "style",
                "severity": "low",
                "message": "Remove console.log() statements before production.",
            })

    return {
        "status": "ready_for_analysis",
        "language": lang,
        "focus": foc,
        "line_count": line_count,
        "static_findings": static_findings,
        "code_preview": code[:500] + ("..." if len(code) > 500 else ""),
        "instruction": (
            f"Perform a thorough {foc} code review of the provided {lang} code. "
            "In addition to the static findings above, identify: "
            "1) Logic bugs or edge case issues, "
            "2) Performance bottlenecks, "
            "3) Security vulnerabilities, "
            "4) Style/readability issues (PEP 8 for Python, ESLint rules for JS/TS), "
            "5) Missing error handling. "
            "Provide a corrected/improved version with inline comments explaining changes."
        ),
    }


def compare_tech_options(
    options: list[str],
    use_case: str,
    criteria: Optional[list[str]] = None,
) -> dict:
    """
    Compare technology options for a given use case across key criteria.

    Args:
        options: List of technologies/tools to compare (e.g. ['FastAPI', 'Flask', 'Django']).
        use_case: What you're building (e.g. 'REST API for a data pipeline', 'ETL orchestrator').
        criteria: Optional list of comparison criteria. Defaults to
                  ['performance', 'learning_curve', 'ecosystem', 'production_readiness'].

    Returns:
        A dict with 'status', 'options', 'use_case', and 'instruction' to generate
        the comparison table.
    """
    if not options:
        return {"status": "error", "message": "No options provided to compare."}

    default_criteria = ["performance", "learning_curve", "ecosystem", "community_support",
                        "production_readiness", "best_for"]
    comparison_criteria = criteria if criteria else default_criteria

    # Known technology metadata
    tech_metadata = {
        "fastapi": {"type": "Python web framework", "focus": "async REST APIs"},
        "flask": {"type": "Python micro-framework", "focus": "lightweight web apps"},
        "django": {"type": "Python full-stack framework", "focus": "full web apps with ORM"},
        "airflow": {"type": "Workflow orchestrator", "focus": "batch ETL pipelines"},
        "prefect": {"type": "Workflow orchestrator", "focus": "modern data pipelines"},
        "dagster": {"type": "Data orchestrator", "focus": "data assets and observability"},
        "dbt": {"type": "SQL transformation tool", "focus": "ELT data transformations"},
        "spark": {"type": "Distributed compute", "focus": "big data processing"},
        "duckdb": {"type": "In-process OLAP DB", "focus": "local analytics on files"},
        "polars": {"type": "DataFrame library", "focus": "fast local data processing"},
        "pandas": {"type": "DataFrame library", "focus": "data manipulation and analysis"},
        "terraform": {"type": "IaC tool", "focus": "cloud infrastructure provisioning"},
        "pulumi": {"type": "IaC tool", "focus": "infrastructure as real code"},
    }

    options_metadata = {
        opt: tech_metadata.get(opt.lower(), {"type": "Technology", "focus": "general purpose"})
        for opt in options
    }

    return {
        "status": "ready",
        "options": options,
        "use_case": use_case,
        "criteria": comparison_criteria,
        "options_metadata": options_metadata,
        "instruction": (
            f"Compare these technologies for the use case: '{use_case}'. "
            f"Options: {', '.join(options)}. "
            f"Evaluation criteria: {', '.join(comparison_criteria)}. "
            "Format as a markdown comparison table with a clear winner recommendation. "
            "Consider the user's background: Python expert, Data Engineer/Analyst, "
            "uses AWS/GCP, Apple ecosystem. "
            "End with a 'Recommendation' section with a direct answer and rationale."
        ),
    }


def get_streaming_setup_advice(
    device: str,
    issue: Optional[str] = None,
    goal: Optional[str] = None,
) -> dict:
    """
    Get setup advice, troubleshooting tips, or optimization recommendations for
    streaming devices and home media setups.

    Args:
        device: The streaming device or system (e.g. 'Apple TV 4K', 'Plex', 'HomePod',
                'Synology NAS', 'Chromecast', 'Roku').
        issue: Optional issue to troubleshoot (e.g. 'buffering on 4K content', 'AirPlay dropping').
        goal: Optional goal to achieve (e.g. 'set up home theater', 'stream from NAS').

    Returns:
        A dict with 'status', 'device', and 'advice' with setup steps and tips.
    """
    device_tips = {
        "apple tv": {
            "best_practices": [
                "Use Ethernet over Wi-Fi for 4K HDR content if possible.",
                "Enable 'Match Content' (Frame Rate and Dynamic Range) in Settings → Video & Audio.",
                "Use tvOS's built-in calibration for your display.",
                "HomeKit Secure Video works natively — link cameras via Home app.",
            ],
            "common_issues": {
                "buffering": "Check network speed (need 25 Mbps+ for 4K). Use Ethernet. Reduce router distance.",
                "airplay dropping": "Ensure both devices are on 5GHz Wi-Fi. Disable VPN on the Apple TV.",
                "remote not working": "Pair manually: hold Menu + Volume Up for 5 seconds.",
            },
            "recommended_apps": ["Infuse 7 (for local media)", "Plex", "Channels DVR", "YouTube TV"],
        },
        "plex": {
            "best_practices": [
                "Run Plex Media Server on a machine with hardware transcoding support (Intel Quick Sync or NVIDIA NVENC).",
                "Set up 'Direct Play' for clients on the same network to avoid transcoding.",
                "Use naming convention: 'Movie Name (Year)/Movie Name (Year).mkv' for best metadata matching.",
                "Enable 'Empty trash automatically after every scan'.",
            ],
            "common_issues": {
                "buffering": "Enable hardware-accelerated transcoding in Plex settings. Check server CPU.",
                "metadata wrong": "Use the Fix Incorrect Match option, or rename files per Plex naming conventions.",
                "no remote access": "Port forward 32400 on your router or use Plex Relay.",
            },
        },
        "default": {
            "best_practices": [
                "Use wired Ethernet for the media server if possible.",
                "Ensure firmware is up to date.",
                "Check router QoS settings to prioritize streaming traffic.",
            ],
            "common_issues": {},
        },
    }

    dev_key = next((k for k in device_tips if k in device.lower()), "default")
    tips = device_tips[dev_key]

    response = {
        "status": "success",
        "device": device,
        "best_practices": tips.get("best_practices", []),
        "recommended_apps": tips.get("recommended_apps", []),
    }

    if issue:
        issue_lower = issue.lower()
        matching_fix = next(
            (v for k, v in tips.get("common_issues", {}).items() if k in issue_lower),
            None,
        )
        response["issue_advice"] = matching_fix or f"No specific fix found for '{issue}'. Describe the issue in more detail."

    if goal:
        response["goal_guidance"] = (
            f"Goal: {goal}. "
            f"Providing tailored setup steps for {device} to achieve this."
        )
        response["instruction"] = (
            f"The user wants to: {goal}. "
            f"Device: {device}. "
            "Provide step-by-step setup instructions specific to this goal. "
            "Include any app downloads, settings to change, and common pitfalls."
        )

    return response
