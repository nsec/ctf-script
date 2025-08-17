import os
import shutil

import typer
from typing_extensions import Annotated

from ctf import ENV
from ctf.logger import LOG
from ctf.utils import get_ctf_script_templates_directory

app = typer.Typer()


@app.command(
    help="Initialize a directory with the default CTF structure. If the directory does not exist, it will be created."
)
def init(
    path: Annotated[
        str, typer.Argument(help="Directory in which to initialize a CTF")
    ] = "",
    force: Annotated[
        bool,
        typer.Option(
            "--force", help="Overwrite the directory if it's already initialized"
        ),
    ] = False,
) -> None:
    # If path is not set, take the one from --location or CTF_ROOT_DIR, else it's the current directory.
    if not path:
        path = (
            str(ENV.get("CTF_ROOT_DIR"))
            if "CTF_ROOT_DIR" in ENV
            else os.path.join(os.getcwd(), ".")
        )

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
            exit(code=1)

        for asset in os.listdir(
            p := os.path.join(get_ctf_script_templates_directory(), "init")
        ):
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
