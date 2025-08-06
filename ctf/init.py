import os
import shutil

import typer
from typing_extensions import Annotated

from ctf import LOG
from ctf.utils import CTF_ROOT_DIRECTORY, TEMPLATES_ROOT_DIRECTORY

app = typer.Typer()


@app.command(
    help="Initialize a directory with the default CTF structure. If the directory does not exist, it will be created."
)
def init(
    path: Annotated[
        str, typer.Argument(help="Directory in which to initialize a CTF")
    ] = CTF_ROOT_DIRECTORY,
    force: Annotated[
        bool,
        typer.Option(
            "--force", help="Overwrite the directory if it's already initialized"
        ),
    ] = False,
) -> None:
    created_directory = False
    created_assets: list[str] = []
    try:
        if not os.path.isdir(path):
            os.mkdir(path)
            LOG.info(f'Creating directory "{path}"')
            created_directory = True
        elif (
            os.path.isdir(os.path.join(path, "challenges"))
            or os.path.isdir(os.path.join(path, ".deploy"))
        ) and not force:
            LOG.error(
                f'Directory "{path}" is already initialized. Use --force to overwrite.'
            )
            LOG.error(force)
            exit(code=1)

        for asset in os.listdir(p := os.path.join(TEMPLATES_ROOT_DIRECTORY, "init")):
            dst_asset = os.path.join(path, asset)
            if os.path.isdir(src_asset := os.path.join(p, asset)):
                shutil.copytree(src_asset, dst_asset, dirs_exist_ok=True)
                LOG.info(f'Created "{dst_asset}" folder')
            else:
                shutil.copy(src_asset, dst_asset)
                LOG.info(f'Created "{dst_asset}" file')

            created_assets.append(dst_asset)

    except Exception:
        import traceback

        if created_directory:
            shutil.rmtree(path)
            LOG.info(f'Removed created "{path}" folder')
        else:
            for asset in created_assets:
                if os.path.isdir(asset):
                    shutil.rmtree(asset)
                    LOG.info(f'Removed created "{asset}" folder')
                else:
                    os.unlink(asset)
                    LOG.info(f'Removed created "{asset}" file')

        LOG.critical(traceback.format_exc())
