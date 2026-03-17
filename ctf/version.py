import typer

from ctf.utils import show_version

app = typer.Typer()


@app.command(help="Print the tool's version.")
def version():
    show_version(True)
