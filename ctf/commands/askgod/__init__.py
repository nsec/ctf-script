import typer

from .stats import app as stats_app

app = typer.Typer(no_args_is_help=True)
app.add_typer(stats_app)
