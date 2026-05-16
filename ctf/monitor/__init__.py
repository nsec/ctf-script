import typer

from .flags import app as flags_app
from .solves import app as solves_app
from .stats import app as stats_app

app = typer.Typer(no_args_is_help=True)
app.add_typer(flags_app)
app.add_typer(stats_app)
app.add_typer(solves_app)
