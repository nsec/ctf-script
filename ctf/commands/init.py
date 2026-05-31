import datetime
import importlib.resources
import shutil
from pathlib import Path

import jinja2
import typer
from typing_extensions import Annotated

from ctf import ENV
from ctf.common.logger import LOG

app = typer.Typer()


@app.command(
    help="Initialize a directory with the default CTF structure. If the directory does not exist, it will be created."
)
def init(
    path: Annotated[
        Path | None, typer.Argument(help="Directory in which to initialize a CTF")
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force", help="Overwrite the directory if it's already initialized"
        ),
    ] = False,
    name: Annotated[
        str,
        typer.Option(
            help="Full display name of the CTF. Example: NorthSec CTF 2027",
            prompt="CTF name (e.g. NorthSec CTF 2027)",
        ),
    ] = f"NorthSec CTF {datetime.datetime.now().year + 1}",
) -> None:
    # If path is not set, take the one from --location or CTF_ROOT_DIR, else it's the current directory.
    if not path:
        path = Path(ENV.get("CTF_ROOT_DIR", "."))

    path = path.expanduser().resolve()

    created_directory = False
    created_assets: list[Path] = []
    try:
        if not path.is_dir():
            LOG.info(f'Creating directory "{path}"')
            path.mkdir()
            created_directory = True
        elif (
            (path / "challenges").is_dir() or (path / ".deploy").is_dir()
        ) and not force:
            LOG.error(
                f'Directory "{path}" is already initialized. Use --force to overwrite.'
            )
            exit(1)

        with importlib.resources.path("ctf.templates", "init") as templates_location:
            jinja_env = jinja2.Environment(
                loader=jinja2.FileSystemLoader(
                    searchpath=templates_location, encoding="utf-8"
                ),
                keep_trailing_newline=True,
            )
            for asset in templates_location.iterdir():
                if asset.suffix == ".j2":
                    dst_asset = path / asset.stem
                    content = jinja_env.get_template(asset.name).render(name=name)
                    with dst_asset.open(mode="w", encoding="utf-8") as f:
                        f.write(content)
                    LOG.info(f'Created "{dst_asset}" file')
                elif asset.is_dir():
                    dst_asset = path / asset.name
                    shutil.copytree(asset, dst_asset, dirs_exist_ok=True)
                    LOG.info(f'Created "{dst_asset}" folder')
                else:
                    dst_asset = path / asset.name
                    shutil.copy(asset, dst_asset)
                    LOG.info(f'Created "{dst_asset}" file')

                created_assets.append(dst_asset)

    except Exception:
        import traceback

        if created_directory:
            shutil.rmtree(path)
            LOG.info(f'Removed created "{path}" folder')
        else:
            for asset in created_assets:
                if asset.is_dir():
                    shutil.rmtree(asset)
                    LOG.info(f'Removed created "{asset}" folder')
                else:
                    asset.unlink()
                    LOG.info(f'Removed created "{asset}" file')

        LOG.critical(traceback.format_exc())
