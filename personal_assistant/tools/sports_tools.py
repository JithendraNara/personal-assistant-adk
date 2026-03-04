"""
Sports tools for the sports_agent.

Covers NFL, Cricket, and F1 scores, standings, and news.
"""

import os
from datetime import datetime, timezone
from typing import Optional

SPORTS_API_KEY = os.getenv("SPORTS_API_KEY", "")
CRICAPI_KEY = os.getenv("CRICAPI_KEY", "")


# ─── Mock Data ──────────────────────────────────────────────────────────────────────────────

_NFL_MOCK_STANDINGS = [
    {"team": "Dallas Cowboys", "division": "NFC East", "wins": 11, "losses": 6, "pct": .647, "streak": "W2"},
    {"team": "Philadelphia Eagles", "division": "NFC East", "wins": 14, "losses": 3, "pct": .824, "streak": "W5"},
    {"team": "Detroit Lions", "division": "NFC North", "wins": 15, "losses": 2, "pct": .882, "streak": "W3"},
    {"team": "Kansas City Chiefs", "division": "AFC West", "wins": 15, "losses": 2, "pct": .882, "streak": "W7"},
    {"team": "Baltimore Ravens", "division": "AFC North", "wins": 12, "losses": 5, "pct": .706, "streak": "L1"},
    {"team": "Buffalo Bills", "division": "AFC East", "wins": 13, "losses": 4, "pct": .765, "streak": "W2"},
]

_F1_MOCK_STANDINGS = {
    "drivers": [
        {"position": 1, "driver": "Max Verstappen", "team": "Red Bull Racing", "points": 437},
        {"position": 2, "driver": "Lando Norris", "team": "McLaren", "points": 374},
        {"position": 3, "driver": "Charles Leclerc", "team": "Ferrari", "points": 356},
        {"position": 4, "driver": "Oscar Piastri", "team": "McLaren", "points": 292},
        {"position": 5, "driver": "Carlos Sainz", "team": "Ferrari", "points": 290},
    ],
    "constructors": [
        {"position": 1, "team": "McLaren", "points": 666},
        {"position": 2, "team": "Ferrari", "points": 652},
        {"position": 3, "team": "Red Bull Racing", "points": 589},
        {"position": 4, "team": "Mercedes", "points": 468},
        {"position": 5, "team": "Aston Martin", "points": 94},
    ],
}


def get_nfl_scores(week: Optional[int] = None, team: Optional[str] = None) -> dict:
    """
    Get NFL game scores and results for a given week or team.

    Args:
        week: NFL regular season week number (1-18). If None, returns most recent week.
        team: Optional team name to filter results (e.g. 'Dallas Cowboys').

    Returns:
        A dict with 'status', 'week', 'games' (list of game result dicts).
    """
    if SPORTS_API_KEY:
        pass

    # Mock games
    current_week = week or 18
    mock_games = [
        {
            "home_team": "Dallas Cowboys",
            "away_team": "Washington Commanders",
            "home_score": 27,
            "away_score": 20,
            "status": "Final",
            "week": current_week,
            "highlight": "Dak Prescott: 28/38, 312 yds, 3 TD",
        },
        {
            "home_team": "Philadelphia Eagles",
            "away_team": "New York Giants",
            "home_score": 35,
            "away_score": 14,
            "status": "Final",
            "week": current_week,
        },
        {
            "home_team": "Kansas City Chiefs",
            "away_team": "Las Vegas Raiders",
            "home_score": 31,
            "away_score": 17,
            "status": "Final",
            "week": current_week,
        },
    ]

    if team:
        team_lower = team.lower()
        mock_games = [
            g for g in mock_games
            if team_lower in g["home_team"].lower() or team_lower in g["away_team"].lower()
        ]

    return {
        "status": "success",
        "week": current_week,
        "season": "2024",
        "games": mock_games,
        "source": "mock — configure SPORTS_API_KEY for live scores",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def get_nfl_standings(conference: Optional[str] = None) -> dict:
    """
    Get current NFL standings, optionally filtered by conference.

    Args:
        conference: Optional filter — 'NFC' or 'AFC'. Returns all if None.

    Returns:
        A dict with 'status', 'season', 'standings' (list of team standing dicts).
    """
    standings = _NFL_MOCK_STANDINGS.copy()
    if conference:
        conf_upper = conference.upper()
        standings = [s for s in standings if s["division"].startswith(conf_upper)]

    # Sort by win percentage
    standings = sorted(standings, key=lambda x: -x["pct"])

    # Flag Cowboys
    cowboys = next((s for s in standings if s["team"] == "Dallas Cowboys"), None)
    note = None
    if cowboys:
        pos = standings.index(cowboys) + 1
        note = f"Cowboys are #{pos} in the shown standings ({cowboys['wins']}-{cowboys['losses']})."

    return {
        "status": "success",
        "season": "2024",
        "conference": conference or "All",
        "standings": standings,
        "cowboys_note": note,
        "source": "mock — configure SPORTS_API_KEY for live standings",
    }


def get_f1_standings(category: str = "drivers") -> dict:
    """
    Get current Formula 1 championship standings.

    Args:
        category: 'drivers' for Drivers' Championship or 'constructors' for
                  Constructors' Championship.

    Returns:
        A dict with 'status', 'season', 'category', and 'standings' list.
    """
    cat = category.lower()
    if cat not in ("drivers", "constructors"):
        cat = "drivers"

    standings = _F1_MOCK_STANDINGS.get(cat, [])

    # Highlight followed teams
    followed_teams = ["Red Bull Racing", "McLaren"]
    for entry in standings:
        team_name = entry.get("team", "")
        entry["following"] = team_name in followed_teams

    last_race = {
        "round": 24,
        "name": "Abu Dhabi Grand Prix",
        "winner": "Lando Norris",
        "team": "McLaren",
        "date": "2024-12-08",
        "fastest_lap": "Oscar Piastri",
    }

    return {
        "status": "success",
        "season": "2024",
        "category": cat,
        "standings": standings,
        "last_race": last_race,
        "source": "mock — configure SPORTS_API_KEY for live F1 data",
    }


def get_cricket_scores(
    match_type: str = "all",
    team: str = "India",
) -> dict:
    """
    Get recent cricket match scores and series information.

    Args:
        match_type: Filter by format — 'test', 't20', 'odi', or 'all'.
        team: National team to focus on (default 'India').

    Returns:
        A dict with 'status', 'team', 'recent_matches', 'upcoming_matches'.
    """
    if CRICAPI_KEY:
        pass

    mock_recent = [
        {
            "match": f"India vs Australia — 3rd Test",
            "format": "test",
            "venue": "Sydney Cricket Ground",
            "result": "India won by 5 wickets",
            "india_batting": "IND 1st innings: 405/8d (Rohit 112, Virat 89)",
            "highlights": "Jasprit Bumrah: 5/45 in 2nd innings",
            "date": "2025-01-05",
        },
        {
            "match": "India vs England — 2nd T20I",
            "format": "t20",
            "venue": "Wankhede Stadium, Mumbai",
            "result": "India won by 34 runs",
            "india_batting": "IND: 196/4 (Suryakumar 82*)",
            "highlights": "Suryakumar Yadav: 82* off 47 balls",
            "date": "2025-02-12",
        },
    ]

    mock_upcoming = [
        {
            "match": "India vs New Zealand — 1st ODI",
            "format": "odi",
            "venue": "Rajiv Gandhi Intl. Cricket Stadium, Hyderabad",
            "date": "2025-03-10",
            "series": "India vs NZ ODI Series 2025",
        },
    ]

    if match_type != "all":
        mock_recent = [m for m in mock_recent if m["format"] == match_type.lower()]
        mock_upcoming = [m for m in mock_upcoming if m["format"] == match_type.lower()]

    return {
        "status": "success",
        "team": team,
        "match_type_filter": match_type,
        "recent_matches": mock_recent,
        "upcoming_matches": mock_upcoming,
        "source": "mock — configure CRICAPI_KEY for live scores",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
