import typer

from .new import app as new_app

app = typer.Typer(no_args_is_help=True)
app.add_typer(new_app)
