import typer

from ctf import VERSION

app = typer.Typer()


@app.command(help="Print the tool's version.")
def version():
    print(VERSION)
    exit(0)
