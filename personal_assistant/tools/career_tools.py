"""
Career and job search tools for the career_agent.

Includes job search, skill matching, and resume/interview utilities.
"""

import os
from datetime import datetime, timezone
from typing import Optional

# REAL API: LinkedIn API, Indeed API, or job board aggregators
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")


# ─── Reference Data ─────────────────────────────────────────────────────────────────────────

SKILL_MARKET_DATA = {
    "Python": {"demand": "very high", "avg_salary_range": "$95k–$165k", "trend": "growing"},
    "SQL": {"demand": "high", "avg_salary_range": "$85k–$150k", "trend": "stable"},
    "Terraform": {"demand": "high", "avg_salary_range": "$110k–$175k", "trend": "growing"},
    "Node.js": {"demand": "high", "avg_salary_range": "$90k–$155k", "trend": "stable"},
    ".NET": {"demand": "medium-high", "avg_salary_range": "$90k–$155k", "trend": "stable"},
    "dbt": {"demand": "high", "avg_salary_range": "$110k–$175k", "trend": "growing fast"},
    "Spark": {"demand": "high", "avg_salary_range": "$120k–$185k", "trend": "stable"},
    "Databricks": {"demand": "high", "avg_salary_range": "$115k–$180k", "trend": "growing"},
    "Snowflake": {"demand": "very high", "avg_salary_range": "$110k–$175k", "trend": "growing"},
    "Airflow": {"demand": "high", "avg_salary_range": "$110k–$170k", "trend": "stable"},
    "AWS": {"demand": "very high", "avg_salary_range": "$110k–$185k", "trend": "growing"},
    "GCP": {"demand": "high", "avg_salary_range": "$115k–$185k", "trend": "growing"},
    "Azure": {"demand": "high", "avg_salary_range": "$110k–$180k", "trend": "stable"},
    "Kubernetes": {"demand": "high", "avg_salary_range": "$120k–$190k", "trend": "stable"},
    "Docker": {"demand": "high", "avg_salary_range": "$100k–$165k", "trend": "stable"},
}

ROLE_TITLES = [
    "Data Engineer",
    "Senior Data Engineer",
    "Staff Data Engineer",
    "Data Analyst",
    "Senior Data Analyst",
    "Analytics Engineer",
    "Software Engineer",
    "Senior Software Engineer",
    "Data Platform Engineer",
    "ML Engineer",
    "Data Architect",
]


def search_jobs(
    title: str,
    location: str = "Remote",
    experience_level: str = "mid",
    remote_only: bool = False,
) -> dict:
    """
    Search for job openings matching the given title and location.

    Args:
        title: Job title to search for (e.g. 'Senior Data Engineer').
        location: City/state or 'Remote' (e.g. 'Fort Wayne, IN', 'Dallas, TX').
        experience_level: One of 'entry', 'mid', 'senior', 'staff', 'principal'.
        remote_only: If True, only return remote positions.

    Returns:
        A dict with 'status', 'query', and 'jobs' (list of job listing dicts).
    """
    if RAPIDAPI_KEY:
        # REAL API: LinkedIn Jobs API via RapidAPI or JSearch
        # import httpx
        # url = "https://jsearch.p.rapidapi.com/search"
        # headers = {"X-RapidAPI-Key": RAPIDAPI_KEY, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}
        # params = {"query": f"{title} in {location}", "page": "1", "num_pages": "1"}
        # r = httpx.get(url, headers=headers, params=params)
        # ... parse and return
        pass

    # Mock job listings based on the user's background
    mock_jobs = [
        {
            "title": f"{title}",
            "company": company,
            "location": loc,
            "remote": remote_only or "Remote" in loc,
            "experience_level": experience_level,
            "salary_range": SKILL_MARKET_DATA.get("Python", {}).get("avg_salary_range", "N/A"),
            "posted": datetime.now(timezone.utc).isoformat(),
            "url": f"https://linkedin.com/jobs/mock-{i}",
            "key_skills": ["Python", "SQL", "Spark", "AWS"] if "Data" in title else ["Python", "Node.js", "AWS"],
        }
        for i, (company, loc) in enumerate([
            ("Capital One", "McLean, VA (Remote)"),
            ("Amazon", "Seattle, WA (Hybrid)"),
            ("Databricks", "Remote"),
            ("Snowflake", "Remote"),
            ("Cigna", "Remote"),
        ])
    ]

    if remote_only:
        mock_jobs = [j for j in mock_jobs if j["remote"]]

    return {
        "status": "success",
        "query": {"title": title, "location": location, "experience_level": experience_level},
        "total_found": len(mock_jobs),
        "jobs": mock_jobs,
        "source": "mock — configure RAPIDAPI_KEY for live job listings",
        "tip": "Filter by 'remote_only=True' for fully remote roles.",
    }


def analyze_skill_gaps(
    target_role: str,
    current_skills: list[str],
) -> dict:
    """
    Compare current skills against requirements for a target role and identify gaps.

    Args:
        target_role: The role to target (e.g. 'Senior Data Engineer', 'Staff Analytics Engineer').
        current_skills: List of skills the candidate currently has.

    Returns:
        A dict with 'status', 'target_role', 'matched_skills', 'gap_skills',
        'priority_gaps', and 'learning_resources'.
    """
    # Role-to-skills mapping (common requirements)
    role_requirements = {
        "data engineer": ["Python", "SQL", "Spark", "dbt", "Airflow", "AWS", "Snowflake", "Docker"],
        "senior data engineer": ["Python", "SQL", "Spark", "dbt", "Airflow", "AWS", "Snowflake", "Kubernetes", "Terraform"],
        "analytics engineer": ["SQL", "dbt", "Python", "Snowflake", "Looker", "data modeling"],
        "data analyst": ["SQL", "Python", "Tableau", "statistics", "Excel"],
        "software engineer": ["Python", "Node.js", "Docker", "AWS", "system design", "REST APIs"],
        "ml engineer": ["Python", "PyTorch", "Spark", "MLflow", "Docker", "Kubernetes"],
    }

    # Normalize lookup
    role_key = target_role.lower()
    required = None
    for key, skills in role_requirements.items():
        if key in role_key:
            required = skills
            break

    if not required:
        required = ["Python", "SQL", "Cloud platform", "Communication", "System design"]

    current_normalized = [s.lower() for s in current_skills]
    matched = [s for s in required if s.lower() in current_normalized]
    gaps = [s for s in required if s.lower() not in current_normalized]

    # Prioritize gaps by market demand
    priority_gaps = sorted(
        gaps,
        key=lambda s: {"very high": 0, "high": 1, "medium-high": 2, "medium": 3}.get(
            SKILL_MARKET_DATA.get(s, {}).get("demand", "medium"), 3
        ),
    )

    # Learning resources for top gaps
    resources = {
        "dbt": "https://courses.getdbt.com — free official dbt courses",
        "Airflow": "https://airflow.apache.org/docs — official docs + Astronomer courses",
        "Kubernetes": "https://kubernetes.io/training — official training",
        "Terraform": "https://developer.hashicorp.com/terraform/tutorials",
        "Snowflake": "https://learn.snowflake.com — Snowflake University (free)",
        "Spark": "https://sparkbyexamples.com — practical Spark tutorials",
        "Databricks": "https://academy.databricks.com — free Databricks Academy",
    }

    learning_plan = [
        {"skill": g, "resource": resources.get(g, f"Search: '{g} tutorial site:coursera.org OR site:udemy.com'")}
        for g in priority_gaps[:5]
    ]

    return {
        "status": "success",
        "target_role": target_role,
        "required_skills": required,
        "matched_skills": matched,
        "gap_skills": gaps,
        "match_pct": round(len(matched) / len(required) * 100, 1) if required else 0,
        "priority_gaps": priority_gaps[:5],
        "learning_plan": learning_plan,
    }


def get_salary_benchmark(
    role: str,
    location: str = "Remote",
    years_experience: int = 5,
) -> dict:
    """
    Get salary benchmark data for a given role, location, and experience level.

    Args:
        role: Job title to benchmark (e.g. 'Senior Data Engineer').
        location: City/state or 'Remote' (e.g. 'Dallas, TX').
        years_experience: Years of relevant experience.

    Returns:
        A dict with 'status', 'role', 'location', 'salary_range', 'percentiles',
        and 'negotiation_tips'.
    """
    # Base ranges by seniority (simplified — real data would come from Levels.fyi, Glassdoor, etc.)
    base_ranges = {
        "data analyst": (70000, 120000),
        "senior data analyst": (95000, 145000),
        "data engineer": (95000, 150000),
        "senior data engineer": (125000, 185000),
        "staff data engineer": (155000, 220000),
        "analytics engineer": (100000, 155000),
        "software engineer": (95000, 150000),
        "senior software engineer": (125000, 185000),
    }

    role_key = role.lower()
    low, high = base_ranges.get(
        next((k for k in base_ranges if k in role_key), "data engineer"),
        (95000, 150000),
    )

    # Adjust for location
    location_multipliers = {
        "new york": 1.25, "san francisco": 1.35, "seattle": 1.2,
        "austin": 1.05, "dallas": 1.05, "chicago": 1.1,
        "fort wayne": 0.85, "remote": 1.0,
    }
    loc_key = location.lower()
    multiplier = next(
        (v for k, v in location_multipliers.items() if k in loc_key),
        0.95,
    )

    # Adjust for experience
    exp_factor = min(1 + (years_experience - 3) * 0.04, 1.4)

    adj_low = int(low * multiplier * exp_factor)
    adj_high = int(high * multiplier * exp_factor)
    adj_median = int((adj_low + adj_high) / 2)

    return {
        "status": "success",
        "role": role,
        "location": location,
        "years_experience": years_experience,
        "salary_range": {"low": adj_low, "median": adj_median, "high": adj_high},
        "percentiles": {
            "25th": int(adj_low * 0.95),
            "50th": adj_median,
            "75th": int(adj_high * 0.95),
            "90th": adj_high,
        },
        "sources": ["Levels.fyi", "Glassdoor", "LinkedIn Salary"],
        "negotiation_tips": [
            "Anchor to the 75th percentile as your opening ask.",
            "Factor in total comp: RSUs, bonus, 401k match, remote flexibility.",
            "Use offers as leverage — get competing offers before negotiating.",
            "For contract roles, target 1.4–1.6x the equivalent FTE hourly rate.",
        ],
        "disclaimer": "These are estimates. Verify with Levels.fyi or Glassdoor for current data.",
    }
