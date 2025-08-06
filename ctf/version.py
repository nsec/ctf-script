import typer

app = typer.Typer()


@app.command(help="Print the tool's version.")
def version():
    # Create an empty command as the version is printed before anything else in the __init__.py file.
    pass
