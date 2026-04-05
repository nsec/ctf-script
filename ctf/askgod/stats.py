import json
from datetime import datetime, timezone

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
    html: Annotated[
        bool, typer.Option("--html", help="Generate an HTML report (stats.html).")
    ] = False,
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
    ai_agent_scores = [s for s in scores if s["ai_agent"]]
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

    flags_with_ai_solves = len(set(s["flag_id"] for s in ai_agent_scores))
    total_flags_solved = len(set(s["flag_id"] for s in scores))
    stats["flags_with_ai_agent_solves"] = flags_with_ai_solves
    stats["total_flags_solved"] = total_flags_solved
    stats["percentage_of_flags_with_ai_agent_solves"] = (
        round(flags_with_ai_solves / total_flags_solved * 100) if scores else 0
    )

    # Bucket submissions into 4-second intervals and compute AI% per bucket
    bucket_size = 10
    buckets: dict[int, dict] = {}
    for score in scores:
        t = datetime.fromisoformat(score["submit_time"].replace("Z", "+00:00"))
        epoch = int(t.timestamp())
        bucket_key = (epoch // bucket_size) * bucket_size
        if bucket_key not in buckets:
            buckets[bucket_key] = {"ai_count": 0, "total_count": 0}
        buckets[bucket_key]["total_count"] += 1
        if score["ai_agent"]:
            buckets[bucket_key]["ai_count"] += 1
    stats["ai_agent_percentage_over_time"] = [
        {
            "bucket_start": datetime.fromtimestamp(k, tz=timezone.utc).strftime(
                "%a %H:%M:%S"
            ),
            "ai_count": v["ai_count"],
            "total_count": v["total_count"],
            "ai_percentage": round(v["ai_count"] / v["total_count"] * 100),
        }
        for k, v in sorted(buckets.items())
    ]

    rich.print(stats)

    if html:
        html_content = generate_html(stats)
        with open("stats.html", "w") as f:
            f.write(html_content)
        LOG.info("HTML report written to stats.html")


def generate_html(stats: dict) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    quintile_labels = ["Bottom 20%", "20-40%", "40-60%", "60-80%", "Top 20%"]

    points_ai_pct = [
        stats["ai_agent_points_per_quintile"][f"quintile_{i}"][
            "ai_agent_points_percentage"
        ]
        for i in range(1, 6)
    ]
    points_human_pct = [
        100
        - stats["ai_agent_points_per_quintile"][f"quintile_{i}"][
            "ai_agent_points_percentage"
        ]
        for i in range(1, 6)
    ]

    scores_ai_pct = [
        stats["ai_agent_scores_per_quintile"][f"quintile_{i}"][
            "ai_agent_scores_percentage"
        ]
        for i in range(1, 6)
    ]
    scores_human_pct = [
        100
        - stats["ai_agent_scores_per_quintile"][f"quintile_{i}"][
            "ai_agent_scores_percentage"
        ]
        for i in range(1, 6)
    ]

    per_point = stats["ai_agent_solve_per_point"]
    point_labels = [str(k) for k in per_point if k > 0]
    point_ai_pct = [
        per_point[k]["ai_agent_solve_percentage"] for k in per_point if k > 0
    ]
    point_human_pct = [100 - v for v in point_ai_pct]

    over_time = stats["ai_agent_percentage_over_time"]
    time_labels = [b["bucket_start"] for b in over_time]
    time_ai_pct = [b["ai_percentage"] for b in over_time]
    time_human_pct = [100 - v for v in time_ai_pct]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Agent Stats</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{
    font-family: system-ui, -apple-system, sans-serif;
    background: #f1f5f9;
    color: #1e293b;
    margin: 0 auto;
    padding: 2rem;
    max-width: 150em;
  }}
  h1 {{ margin: 0 0 0.25rem; font-size: 1.75rem; font-weight: 700; }}
  .subtitle {{ color: #64748b; font-size: 0.9rem; margin-bottom: 2rem; }}
  .cards {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 1rem;
    margin-bottom: 2rem;
  }}
  .card {{
    background: #fff;
    border-radius: 10px;
    padding: 1.25rem 1rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }}
  .card .value {{
    font-size: 2rem;
    font-weight: 700;
    color: #2563eb;
    line-height: 1;
    margin-bottom: 0.35rem;
  }}
  .card .label {{
    font-size: 0.78rem;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }}
  .card .secondary {{
    font-size: 0.85rem;
    color: #94a3b8;
    margin-top: 0.25rem;
  }}
  .charts-row {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin-bottom: 1rem;
  }}
  .chart-box {{
    background: #fff;
    border-radius: 10px;
    padding: 1.5rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  }}
  .chart-box h2 {{
    font-size: 1rem;
    font-weight: 600;
    margin: 0 0 1rem;
    color: #334155;
  }}
  @media (max-width: 700px) {{
    .charts-row {{ grid-template-columns: 1fr; }}
  }}
</style>
</head>
<body>
<h1>AI Agent Stats</h1>
<p class="subtitle">Generated {timestamp}</p>

<div class="cards">
  <div class="card"><div class="value">{stats["ai_agent_score_percentage"]}%</div><div class="label">Valid Flags submitted by an AI agent</div><div class="secondary">{stats["ai_agent_scores"]} / {stats["total_scores"]}</div></div>
  <div class="card"><div class="value">{stats["ai_agent_points_percentage"]}%</div><div class="label">Points scored by AI Agents</div><div class="secondary">{stats["ai_agent_points"]} / {stats["total_points"]}</div></div>
  <div class="card"><div class="value">{stats["teams_with_ai_agent_scores_percentage"]}%</div><div class="label">Teams Using AI Agents</div><div class="secondary">{stats["teams_with_ai_agent_scores"]} / {stats["total_teams"]}</div></div>
  <div class="card"><div class="value">{stats["percentage_of_flags_with_ai_agent_solves"]}%</div><div class="label">Solved Flags w/ at least one agent Solve</div><div class="secondary">{stats["flags_with_ai_agent_solves"]} / {stats["total_flags_solved"]}</div></div>
</div>

<div class="charts-row">
  <div class="chart-box">
    <h2>Points per Quintile</h2>
    <canvas id="pointsChart"></canvas>
  </div>
  <div class="chart-box">
    <h2>Solves per Quintile</h2>
    <canvas id="scoresChart"></canvas>
  </div>
</div>

<div class="charts-row">
  <div class="chart-box">
    <h2>AI Solve % by Flag Point Value</h2>
    <canvas id="perPointChart"></canvas>
  </div>
  <div class="chart-box">
    <h2>AI Submission % over Time (4s buckets)</h2>
    <canvas id="overTimeChart"></canvas>
  </div>
</div>

<script>
const quintileLabels = {json.dumps(quintile_labels)};
const pointsAI = {json.dumps(points_ai_pct)};
const pointsHuman = {json.dumps(points_human_pct)};
const scoresAI = {json.dumps(scores_ai_pct)};
const scoresHuman = {json.dumps(scores_human_pct)};
const pointLabels = {json.dumps(point_labels)};
const pointAIPct = {json.dumps(point_ai_pct)};
const pointHumanPct = {json.dumps(point_human_pct)};
const timeLabels = {json.dumps(time_labels)};
const timeAIPct = {json.dumps(time_ai_pct)};
const timeHumanPct = {json.dumps(time_human_pct)};

const stackedOpts = {{
  responsive: true,
  plugins: {{
    legend: {{ position: 'bottom' }},
    tooltip: {{
      callbacks: {{
        label: ctx => `${{ctx.dataset.label}}: ${{ctx.parsed.y}}%`
      }}
    }}
  }},
  scales: {{
    x: {{ stacked: true }},
    y: {{ stacked: true, beginAtZero: true, max: 100, ticks: {{ callback: v => v + '%' }} }}
  }}
}};

new Chart(document.getElementById('pointsChart'), {{
  type: 'bar',
  data: {{
    labels: quintileLabels,
    datasets: [
      {{ label: 'AI Agent', data: pointsAI, backgroundColor: '#2563eb' }},
      {{ label: 'Human', data: pointsHuman, backgroundColor: '#cbd5e1' }}
    ]
  }},
  options: stackedOpts
}});

new Chart(document.getElementById('scoresChart'), {{
  type: 'bar',
  data: {{
    labels: quintileLabels,
    datasets: [
      {{ label: 'AI Agent', data: scoresAI, backgroundColor: '#2563eb' }},
      {{ label: 'Human', data: scoresHuman, backgroundColor: '#cbd5e1' }}
    ]
  }},
  options: stackedOpts
}});

new Chart(document.getElementById('perPointChart'), {{
  type: 'bar',
  data: {{
    labels: pointLabels,
    datasets: [
      {{ label: 'AI Agent', data: pointAIPct, backgroundColor: '#2563eb' }},
      {{ label: 'Human', data: pointHumanPct, backgroundColor: '#cbd5e1' }}
    ]
  }},
  options: stackedOpts
}});

new Chart(document.getElementById('overTimeChart'), {{
  type: 'bar',
  data: {{
    labels: timeLabels,
    datasets: [
      {{ label: 'AI Agent', data: timeAIPct, backgroundColor: '#2563eb' }},
      {{ label: 'Human', data: timeHumanPct, backgroundColor: '#cbd5e1' }}
    ]
  }},
  options: {{
    ...stackedOpts,
    scales: {{
      ...stackedOpts.scales,
      x: {{ ...stackedOpts.scales.x, ticks: {{ maxRotation: 45, autoSkip: true, maxTicksLimit: 20 }} }}
    }}
  }}
}});
</script>
</body>
</html>"""


def get(session: requests.Session, url: str) -> dict:
    try:
        response = session.get(url=f"{session.base_url}{url}")
        response.raise_for_status()
        return response.json()
    except requests.HTTPError as e:
        e.add_note(f"Failed to fetch stats from {e.request.url}: {e.text}")
        raise e
