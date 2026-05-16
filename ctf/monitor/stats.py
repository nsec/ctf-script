import re
import subprocess
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer()


@app.command(help=".")
def stats(
    tracks: Annotated[
        list[str],
        typer.Option(
            "--tracks",
            "-t",
            help="Tracks to monitor.",
        ),
    ] = [],
    ids: Annotated[
        list[int], typer.Option("-i", "--ids", help="Monitor flags using IDs.")
    ] = [],
) -> None:
    r: subprocess.CompletedProcess[bytes] = subprocess.run(
        ["askgod", "admin", "list-teams"],
        capture_output=True,
        check=True,
    )

    amount_of_teams = int(
        sorted(
            r.stdout.decode().strip().splitlines()[2:],
            reverse=True,
            key=lambda item: int(item.split("|")[0].strip()),
        )[0]
        .split("|")[0]
        .strip()
    )

    r: subprocess.CompletedProcess[bytes] = subprocess.run(
        ["askgod", "admin", "list-flags"],
        capture_output=True,
        check=True,
    )
    for line in r.stdout.decode().strip().splitlines():
        for track in tracks:
            if re.search(r"\|\s*.*" + track, line, re.IGNORECASE):
                ids.append(int(line.split("|")[0]))

    if not ids:
        if not tracks:
            print("You must provide tracks or ids.")
        else:
            print(f"No flag found from given tracks: {', '.join(tracks)}")
        raise typer.Exit(1)

    r: subprocess.CompletedProcess[bytes] = subprocess.run(
        ["askgod", "admin", "list-scores"],
        capture_output=True,
        check=True,
    )

    solves_per_flag = {}
    for line in r.stdout.decode().strip().splitlines():
        try:
            _id = line.split("|")[2].strip()
        except Exception:
            continue

        if not _id.isnumeric():
            continue

        if int(_id) in ids:
            if _id not in solves_per_flag:
                solves_per_flag[_id] = 0
            solves_per_flag[_id] += 1

    table = Table(show_lines=True)
    table.add_column("ID")
    table.add_column("Amount")
    table.add_column("Percent")

    for _id, solves in sorted(
        solves_per_flag.items(), reverse=True, key=lambda item: item[1]
    ):
        table.add_row(_id, str(solves), str(int((solves / amount_of_teams) * 100)))

    Console().print(table)
