import importlib.resources
import os
import re
import secrets
import shutil
from enum import StrEnum
from pathlib import Path

import jinja2
import typer
from typing_extensions import Annotated

from ctf.common.logger import LOG
from ctf.common.utils import find_ctf_root_directory

app = typer.Typer()


class Template(StrEnum):
    INFRA_SKELETON = "infra-skeleton"
    TRACK_YAML_ONLY = "track-yaml-only"
    FILES_ONLY = "files-only"
    APACHE_PHP = "apache-php"
    PYTHON_SERVICE = "python-service"
    RUST_WEBSERVICE = "rust-webservice"
    WINDOWS_VM = "windows-vm"


@app.command(help="Create a new CTF track with a given name")
def new(
    name: Annotated[
        str,
        typer.Option(
            help="Track name. No space, use dashes if needed.",
            prompt="Track name. No space, use dashes if needed.",
        ),
    ],
    template: Annotated[
        Template,
        typer.Option(
            "--template",
            "-t",
            help="Template to use for the track.",
            prompt="Template to use for the track.",
        ),
    ] = Template.INFRA_SKELETON,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            help="If directory already exists, delete it and create it again.",
        ),
    ] = False,
    with_build_container: Annotated[
        bool,
        typer.Option(
            "--with-build",
            help="If a build container is required.",
        ),
    ] = False,
    with_virtual_machine: Annotated[
        bool,
        typer.Option(
            "--vm",
            "--with-virtual-machine",
            help="If a virtual machine is required.",
        ),
    ] = False,
) -> None:
    LOG.info(f"Creating a new track: {name}")
    if not re.match(pattern=r"^[a-z][a-z0-9\-]{0,61}[a-z0-9]$", string=name):
        LOG.critical(
            """The track name Valid instance names must fulfill the following requirements:
* The name must be between 1 and 63 characters long;
* The name must contain only letters, numbers and dashes from the ASCII table;
* The name must not start with a digit or a dash;
* The name must not end with a dash."""
        )
        exit(1)

    if template == Template.RUST_WEBSERVICE:
        with_build_container = True

    if (
        new_challenge_directory := find_ctf_root_directory() / "challenges" / name
    ).exists():
        if force:
            LOG.debug(f"Deleting {new_challenge_directory}")
            shutil.rmtree(new_challenge_directory)
        else:
            LOG.critical(
                "Track already exists with that name. Use `--force` to overwrite the track."
            )
            exit(1)

    new_challenge_directory.mkdir()

    LOG.debug(f"Directory {new_challenge_directory} created.")

    with importlib.resources.path("ctf.templates", "new") as templates_location:
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                searchpath=templates_location, encoding="utf-8"
            )
        )

        ipv6_subnet = f"9000:d37e:c40b:{secrets.choice('0123456789abcdef')}{secrets.choice('0123456789abcdef')}{secrets.choice('0123456789abcdef')}{secrets.choice('0123456789abcdef')}"

        rb = [
            secrets.choice("0123456789abcdef"),
            secrets.choice("0123456789abcdef"),
            secrets.choice("0123456789abcdef"),
            secrets.choice("0123456789abcdef"),
            secrets.choice("0123456789abcdef"),
            secrets.choice("0123456789abcdef"),
            secrets.choice("0123456789abcdef"),
            secrets.choice("0123456789abcdef"),
            secrets.choice("0123456789abcdef"),
            secrets.choice("0123456789abcdef"),
            secrets.choice("0123456789abcdef"),
            secrets.choice("0123456789abcdef"),
        ]
        hardware_address = f"00:16:3e:{rb[0]}{rb[1]}:{rb[2]}{rb[3]}:{rb[4]}{rb[5]}"
        ipv6_address = f"216:3eff:fe{rb[0]}{rb[1]}:{rb[2]}{rb[3]}{rb[4]}{rb[5]}"
        full_ipv6_address = f"{ipv6_subnet}:{ipv6_address}"

        track_template = env.get_template(os.path.join("common", "track.yaml.j2"))
        render = track_template.render(
            data={
                "name": name,
                "full_ipv6_address": full_ipv6_address,
                "hardware_address": hardware_address,
                "is_windows": template == Template.WINDOWS_VM,
                "template": template.value,
                "with_build": with_build_container,
                "with_virtual_machine": with_virtual_machine,
            }
        )
        with (p := new_challenge_directory / "track.yaml").open(
            mode="w", encoding="utf-8"
        ) as f:
            f.write(render)

        LOG.debug(f"Wrote {p}.")

        readme_template = env.get_template(name=os.path.join("common", "README.md.j2"))
        render = readme_template.render(data={"name": name})
        with (p := new_challenge_directory / "README.md").open(
            mode="w", encoding="utf-8"
        ) as f:
            f.write(render)

        LOG.debug(f"Wrote {p}.")

        posts_directory: Path = new_challenge_directory / "posts"
        posts_directory.mkdir()

        LOG.debug(f"Directory {posts_directory} created.")

        track_template = env.get_template(name=os.path.join("common", "topic.yaml.j2"))
        render = track_template.render(data={"name": name})
        with (p := posts_directory / f"{name}.yaml").open(
            mode="w", encoding="utf-8"
        ) as f:
            f.write(render)

        LOG.debug(f"Wrote {p}.")

        track_template = env.get_template(name=os.path.join("common", "post.yaml.j2"))
        render = track_template.render(data={"name": name})
        with (p := posts_directory / f"{name}_flag1.yaml").open(
            mode="w",
            encoding="utf-8",
        ) as f:
            f.write(render)

        LOG.debug(f"Wrote {p}.")

        if template == Template.TRACK_YAML_ONLY:
            return

        files_directory: Path = new_challenge_directory / "files"
        files_directory.mkdir()

        LOG.debug(f"Directory {files_directory} created.")

        if template == Template.FILES_ONLY:
            return

        terraform_directory: Path = new_challenge_directory / "terraform"
        terraform_directory.mkdir()

        LOG.debug(f"Directory {terraform_directory} created.")

        track_template = env.get_template(name=os.path.join("common", "main.tf.j2"))

        render = track_template.render(
            data={
                "name": name,
                "ipv6_subnet": ipv6_subnet,
                "full_ipv6_address": full_ipv6_address,
                "with_build": with_build_container,
                "with_virtual_machine": with_virtual_machine,
                "is_windows": template == Template.WINDOWS_VM,
            }
        )
        with (p := terraform_directory / "main.tf").open(
            mode="w", encoding="utf-8"
        ) as f:
            f.write(render)

        LOG.debug(f"Wrote {p}.")

        relpath = os.path.relpath(
            find_ctf_root_directory() / ".deploy" / "common", terraform_directory
        )

        os.symlink(
            src=os.path.join(relpath, "variables.tf"),
            dst=(p := terraform_directory / "variables.tf"),
        )

        LOG.debug(f"Wrote {p}.")

        os.symlink(
            src=os.path.join(relpath, "versions.tf"),
            dst=(p := terraform_directory / "versions.tf"),
        )

        LOG.debug(f"Wrote {p}.")

        ansible_directory: Path = new_challenge_directory / "ansible"
        ansible_directory.mkdir()

        LOG.debug(f"Directory {ansible_directory} created.")

        track_template = env.get_template(name=os.path.join(template, "deploy.yaml.j2"))
        render = track_template.render(
            data={
                "name": name,
                "with_build": with_build_container,
                "with_virtual_machine": with_virtual_machine,
            }
        )
        with (p := ansible_directory / "deploy.yaml").open(
            mode="w", encoding="utf-8"
        ) as f:
            f.write(render)

        LOG.debug(f"Wrote {p}.")

        if with_build_container:
            try:
                track_template = env.get_template(
                    os.path.join(template, "build.yaml.j2")
                )
            except jinja2.TemplateNotFound:
                track_template = env.get_template(
                    os.path.join("common", "build.yaml.j2")
                )

            render = track_template.render(
                data={"name": name, "with_build": with_build_container}
            )

            with (p := ansible_directory / "build.yaml").open(
                mode="w", encoding="utf-8"
            ) as f:
                f.write(render)
            LOG.debug(f"Wrote {p}.")

        track_template = env.get_template(name=os.path.join("common", "inventory.j2"))
        render = track_template.render(
            data={
                "name": name,
                "with_build": with_build_container,
                "with_virtual_machine": with_virtual_machine,
                "is_windows": template == Template.WINDOWS_VM,
            }
        )
        with (p := ansible_directory / "inventory").open(
            mode="w", encoding="utf-8"
        ) as f:
            f.write(render)

        LOG.debug(f"Wrote {p}.")

        ansible_challenge_directory: Path = ansible_directory / "challenge"
        ansible_challenge_directory.mkdir()

        LOG.debug(f"Directory {ansible_challenge_directory} created.")

        if template == Template.APACHE_PHP:
            track_template = env.get_template(
                os.path.join(Template.APACHE_PHP, "index.php.j2")
            )
            render = track_template.render(data={"name": name})
            with (p := ansible_challenge_directory / "index.php").open(
                mode="w",
                encoding="utf-8",
            ) as f:
                f.write(render)

            LOG.debug(f"Wrote {p}.")

        if template == Template.PYTHON_SERVICE:
            track_template = env.get_template(
                os.path.join(Template.PYTHON_SERVICE, "app.py.j2")
            )
            render = track_template.render(data={"name": name})
            with (p := ansible_challenge_directory / "app.py").open(
                mode="w",
                encoding="utf-8",
            ) as f:
                f.write(render)

            LOG.debug(f"Wrote {p}.")

            with (p := ansible_challenge_directory / "flag-1.txt").open(
                mode="w",
                encoding="utf-8",
            ) as f:
                f.write(f"{{{{ track_flags.{name}_flag_1 }}}} (1/2)\n")

            LOG.debug(f"Wrote {p}.")

        if template == Template.RUST_WEBSERVICE:
            # Copy the entire challenge template
            shutil.copytree(
                templates_location / Template.RUST_WEBSERVICE / "source",
                ansible_challenge_directory,
                dirs_exist_ok=True,
            )
            LOG.debug(f"Wrote files to {ansible_challenge_directory}")

            manifest_template = env.get_template(
                os.path.join(Template.RUST_WEBSERVICE, "Cargo.toml.j2")
            )
            render = manifest_template.render(data={"name": name})
            with (p := ansible_challenge_directory / "Cargo.toml").open(
                mode="w",
                encoding="utf-8",
            ) as f:
                f.write(render)

            LOG.debug(f"Wrote {p}.")
