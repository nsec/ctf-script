import requests
import rich
import typer
from typing_extensions import Annotated

from ctf.logger import LOG

app = typer.Typer()


@app.command(
    help="Show stats from askgod, specifically regarding to AI agent flag submissions."
)
def stats(
    askgod_url: Annotated[
        str, typer.Option("--askgod-url", "-u", help="Askgod server URL.")
    ] = "https://askgod.nsec",
) -> None:
    stats = {}
    session = requests.Session()
    session.base_url = askgod_url + "/1.0"
    LOG.info(f"Fetching stats from {session.base_url}")
    flags = get(session, "/flags")
    scores = get(session, "/scores")
    scoreboard = get(session, "/scoreboard")
    # rich.print(flags)
    # rich.print(scores)
    # rich.print(scoreboard)

    # Join the flags and scores data together based on flag's `id` and score's `flag_id` by modifying the `scores` list in place
    for score in scores:
        flag = next((f for f in flags if f["id"] == score["flag_id"]), None)
        if flag:
            score["flag"] = flag["flag"]
            score["description"] = flag["description"]
            score["return_string"] = flag["return_string"]
        else:
            LOG.warning(
                f"Could not find flag for score with flag_id {score['flag_id']}"
            )
    LOG.info(f"Analyzing {len(scores)} scores...")
    ai_agent_scores = [s for s in scores if s["ai_agent"] == True]
    stats["total_scores"] = len(scores)
    stats["ai_agent_scores"] = len(ai_agent_scores)
    stats["ai_agent_score_percentage"] = (
        round(len(ai_agent_scores) / len(scores) * 100) if scores else 0
    )

    stats["total_points"] = sum(s["value"] for s in scores)
    stats["ai_agent_points"] = sum(s["value"] for s in ai_agent_scores)
    stats["ai_agent_points_percentage"] = (
        round(stats["ai_agent_points"] / stats["total_points"] * 100)
        if stats["total_points"]
        else 0
    )

    stats["total_teams"] = len(set(s["team_id"] for s in scores))
    stats["teams_with_ai_agent_scores"] = len(
        set(s["team_id"] for s in ai_agent_scores)
    )
    stats["teams_with_ai_agent_scores_percentage"] = (
        round(stats["teams_with_ai_agent_scores"] / stats["total_teams"] * 100)
        if stats["total_teams"]
        else 0
    )

    teams_per_quintile = {}
    # Separate teams into quintiles based on the scoreboard. The rank of a team is its position in the index of the scoreboard
    for i in range(5):
        teams_per_quintile[4 - i] = scoreboard[
            len(scoreboard) // 5 * i : len(scoreboard) // 5 * (i + 1)
        ]
    # rich.print(teams_per_quintile)

    stats["ai_agent_points_per_quintile"] = {}
    for i in range(5):
        quintile_team_ids = set(t["team"]["id"] for t in teams_per_quintile[i])
        ai_agent_points_in_quintile = sum(
            s["value"] for s in ai_agent_scores if s["team_id"] in quintile_team_ids
        )
        total_points_in_quintile = sum(
            s["value"] for s in scores if s["team_id"] in quintile_team_ids
        )
        stats["ai_agent_points_per_quintile"][f"quintile_{i + 1}"] = {
            "ai_agent_points": ai_agent_points_in_quintile,
            "total_points": total_points_in_quintile,
            "ai_agent_points_percentage": (
                round(ai_agent_points_in_quintile / total_points_in_quintile * 100)
                if total_points_in_quintile
                else 0
            ),
        }

    stats["ai_agent_scores_per_quintile"] = {}
    for i in range(5):
        quintile_team_ids = set(t["team"]["id"] for t in teams_per_quintile[i])
        ai_agent_scores_in_quintile = sum(
            1 for s in ai_agent_scores if s["team_id"] in quintile_team_ids
        )
        total_scores_in_quintile = sum(
            1 for s in scores if s["team_id"] in quintile_team_ids
        )
        stats["ai_agent_scores_per_quintile"][f"quintile_{i + 1}"] = {
            "ai_agent_scores": ai_agent_scores_in_quintile,
            "total_scores": total_scores_in_quintile,
            "ai_agent_scores_percentage": (
                round(ai_agent_scores_in_quintile / total_scores_in_quintile * 100)
                if total_scores_in_quintile
                else 0
            ),
        }

    stats["ai_agent_solve_per_point"] = {}
    for i in range(21):
        stats["ai_agent_solve_per_point"][i] = {
            "ai_agent_solves": 0,
            "total_solves": 0,
            "ai_agent_solve_percentage": 0,
        }
    for score in scores:
        stats["ai_agent_solve_per_point"][score["value"]]["total_solves"] += 1
        if score["ai_agent"]:
            stats["ai_agent_solve_per_point"][score["value"]]["ai_agent_solves"] += 1
            stats["ai_agent_solve_per_point"][score["value"]][
                "ai_agent_solve_percentage"
            ] = round(
                stats["ai_agent_solve_per_point"][score["value"]]["ai_agent_solves"]
                / stats["ai_agent_solve_per_point"][score["value"]]["total_solves"]
                * 100
            )
    stats["ai_agent_solve_per_point"] = dict(
        sorted(stats["ai_agent_solve_per_point"].items(), key=lambda item: item[0])
    )

    stats["percentage_of_flags_with_ai_agent_solves"] = (
        round(
            len(set(s["flag_id"] for s in ai_agent_scores))
            / len(set(s["flag_id"] for s in scores))
            * 100
        )
        if scores
        else 0
    )

    rich.print(stats)


def get(session: requests.Session, url: str) -> dict:
    try:
        response = session.get(url=f"{session.base_url}{url}")
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        e.add_note(f"Failed to fetch stats from {e.request.url}: {e.text}")
        raise e
