import re
import subprocess
from typing import Annotated

import typer

app = typer.Typer()


@app.command(help="Monitor flags using IDs or track name.")
def flags(
    tracks: Annotated[
        list[str],
        typer.Option(
            "--tracks",
            "-t",
            help="Monitor flags using track name.",
        ),
    ] = [],
    ids: Annotated[
        list[int], typer.Option("-i", "--ids", help="Monitor flags using IDs.")
    ] = [],
) -> None:
    try:
        while True:
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

            print(f"Monitoring IDs: {'|'.join([str(i) for i in ids])}")
            print(
                f"askgod admin monitor-flags | grep -E 'id=({'|'.join([str(i) for i in ids])})'"
            )
            r: subprocess.CompletedProcess[bytes] = subprocess.run(
                f"askgod admin monitor-flags | grep -E 'id=({'|'.join([str(i) for i in ids])})'",
                check=True,
                shell=True,
            )
    except KeyboardInterrupt:
        ...
