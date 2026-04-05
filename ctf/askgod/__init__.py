import typer

from ctf.askgod.stats import app as stats_app

app = typer.Typer()
app.add_typer(stats_app)
