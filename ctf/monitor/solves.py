import os
import subprocess
import sys
import time
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer()


@app.command(help="Monitor solves per track.")
def solves(
    tracks: Annotated[
        list[str],
        typer.Option(
            "--tracks",
            "-t",
            help="Tracks to monitor.",
        ),
    ] = [],
    minimum_solves: Annotated[
        int,
        typer.Option(
            "-m",
            "--minimum-solves",
            help="Displaying tracks that has a threshold equal or higher.",
        ),
    ] = 1,
) -> None:
    try:
        while True:
            r: subprocess.CompletedProcess[bytes] = subprocess.run(
                ["askgod", "admin", "history"],
                capture_output=True,
                check=True,
            )

            solves_per_track: dict[str, dict[tuple[str, str], int]] = {
                track: {} for track in tracks
            }
            for line in r.stdout.decode().split("\n"):
                for track in tracks:
                    if track in line:
                        splitted_line = line.split("|")
                        key: tuple[str, str] = (
                            splitted_line[3].strip().replace("team", "").lstrip("0"),
                            splitted_line[4],
                        )
                        if key not in solves_per_track[track]:
                            solves_per_track[track][key] = 0
                        solves_per_track[track][key] += 1

            os.system("cls" if sys.platform.startswith("win") else "clear")
            table = Table(show_lines=True)
            table.add_column("Track", style="bold cyan")
            table.add_column("Team ID")
            table.add_column("Team Name")
            table.add_column("Solves")
            for track, team_solves in sorted(
                solves_per_track.items(),
                key=lambda item: item[0],
            ):
                for team, solves in sorted(
                    team_solves.items(), reverse=True, key=lambda item: item[1]
                ):
                    if solves > minimum_solves:
                        table.add_row(track, team[0], team[1], str(solves))

            Console().print(table)

            time.sleep(5)
    except KeyboardInterrupt:
        ...
