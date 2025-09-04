import os
import re
import secrets
import shutil
from enum import StrEnum

import jinja2
import typer
from typing_extensions import Annotated

from ctf.logger import LOG
from ctf.utils import find_ctf_root_directory, get_ctf_script_templates_directory

app = typer.Typer()


class Template(StrEnum):
    APACHE_PHP = "apache-php"
    PYTHON_SERVICE = "python-service"
    FILES_ONLY = "files-only"
    TRACK_YAML_ONLY = "track-yaml-only"
    RUST_WEBSERVICE = "rust-webservice"


@app.command(help="Create a new CTF track with a given name")
def new(
    name: Annotated[
        str,
        typer.Option(
            help="Track name. No space, use underscores if needed.",
            prompt="Track name. No space, use underscores if needed.",
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
    ] = Template.APACHE_PHP,
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
) -> None:
    LOG.info(msg=f"Creating a new track: {name}")
    if not re.match(pattern=r"^[a-z][a-z0-9\-]{0,61}[a-z0-9]$", string=name):
        LOG.critical(
            msg="""The track name Valid instance names must fulfill the following requirements:
* The name must be between 1 and 63 characters long;
* The name must contain only letters, numbers and dashes from the ASCII table;
* The name must not start with a digit or a dash;
* The name must not end with a dash."""
        )
        exit(code=1)

    if os.path.exists(
        path=(
            new_challenge_directory := os.path.join(
                find_ctf_root_directory(), "challenges", name
            )
        )
    ):
        if force:
            LOG.debug(msg=f"Deleting {new_challenge_directory}")
            shutil.rmtree(new_challenge_directory)
        else:
            LOG.critical(
                "Track already exists with that name. Use `--force` to overwrite the track."
            )
            exit(code=1)

    os.mkdir(new_challenge_directory)

    LOG.debug(msg=f"Directory {new_challenge_directory} created.")

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(
            searchpath=(
                new_template_path := os.path.join(
                    get_ctf_script_templates_directory(), "new"
                )
            ),
            encoding="utf-8",
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

    track_template = env.get_template(name=os.path.join("common", "track.yaml.j2"))
    render = track_template.render(
        data={
            "name": name,
            "full_ipv6_address": full_ipv6_address,
            "ipv6_subnet": ipv6_subnet,
            "template": template.value,
        }
    )
    with open(
        file=(p := os.path.join(new_challenge_directory, "track.yaml")),
        mode="w",
        encoding="utf-8",
    ) as f:
        f.write(render)

    LOG.debug(msg=f"Wrote {p}.")

    readme_template = env.get_template(name=os.path.join("common", "README.md.j2"))
    render = readme_template.render(data={"name": name})
    with open(
        file=(p := os.path.join(new_challenge_directory, "README.md")),
        mode="w",
        encoding="utf-8",
    ) as f:
        f.write(render)

    LOG.debug(msg=f"Wrote {p}.")

    posts_directory = os.path.join(new_challenge_directory, "posts")

    os.mkdir(path=posts_directory)

    LOG.debug(msg=f"Directory {posts_directory} created.")

    track_template = env.get_template(name=os.path.join("common", "topic.yaml.j2"))
    render = track_template.render(data={"name": name})
    with open(
        file=(p := os.path.join(posts_directory, f"{name}.yaml")),
        mode="w",
        encoding="utf-8",
    ) as f:
        f.write(render)

    LOG.debug(msg=f"Wrote {p}.")

    track_template = env.get_template(name=os.path.join("common", "post.yaml.j2"))
    render = track_template.render(data={"name": name})
    with open(
        file=(p := os.path.join(posts_directory, f"{name}_flag1.yaml")),
        mode="w",
        encoding="utf-8",
    ) as f:
        f.write(render)

    LOG.debug(msg=f"Wrote {p}.")

    if template == Template.TRACK_YAML_ONLY:
        return

    files_directory = os.path.join(new_challenge_directory, "files")

    os.mkdir(path=files_directory)

    LOG.debug(msg=f"Directory {files_directory} created.")

    if template == Template.FILES_ONLY:
        return

    terraform_directory = os.path.join(new_challenge_directory, "terraform")

    os.mkdir(path=terraform_directory)

    LOG.debug(msg=f"Directory {terraform_directory} created.")

    track_template = env.get_template(name=os.path.join("common", "main.tf.j2"))

    render = track_template.render(
        data={
            "name": name,
            "hardware_address": hardware_address,
            "ipv6": ipv6_address,
            "ipv6_subnet": ipv6_subnet,
            "full_ipv6_address": full_ipv6_address,
            "with_build": with_build_container,
        }
    )
    with open(
        file=(p := os.path.join(terraform_directory, "main.tf")),
        mode="w",
        encoding="utf-8",
    ) as f:
        f.write(render)

    LOG.debug(msg=f"Wrote {p}.")

    relpath = os.path.relpath(
        os.path.join(find_ctf_root_directory(), ".deploy", "common"),
        terraform_directory,
    )

    os.symlink(
        src=os.path.join(relpath, "variables.tf"),
        dst=(p := os.path.join(terraform_directory, "variables.tf")),
    )

    LOG.debug(msg=f"Wrote {p}.")

    os.symlink(
        src=os.path.join(relpath, "versions.tf"),
        dst=(p := os.path.join(terraform_directory, "versions.tf")),
    )

    LOG.debug(msg=f"Wrote {p}.")

    ansible_directory = os.path.join(new_challenge_directory, "ansible")

    os.mkdir(path=ansible_directory)

    LOG.debug(msg=f"Directory {ansible_directory} created.")

    track_template = env.get_template(name=os.path.join(template, "deploy.yaml.j2"))
    render = track_template.render(
        data={"name": name, "with_build": with_build_container}
    )
    with open(
        file=(p := os.path.join(ansible_directory, "deploy.yaml")),
        mode="w",
        encoding="utf-8",
    ) as f:
        f.write(render)

    LOG.debug(msg=f"Wrote {p}.")

    if with_build_container:
        track_template = env.get_template(name=os.path.join("common", "build.yaml.j2"))
        render = track_template.render(
            data={"name": name, "with_build": with_build_container}
        )
        with open(
            file=(p := os.path.join(ansible_directory, "build.yaml")),
            mode="w",
            encoding="utf-8",
        ) as f:
            f.write(render)
        LOG.debug(msg=f"Wrote {p}.")

    track_template = env.get_template(name=os.path.join("common", "inventory.j2"))
    render = track_template.render(
        data={"name": name, "with_build": with_build_container}
    )
    with open(
        file=(p := os.path.join(ansible_directory, "inventory")),
        mode="w",
        encoding="utf-8",
    ) as f:
        f.write(render)

    LOG.debug(msg=f"Wrote {p}.")

    ansible_challenge_directory = os.path.join(ansible_directory, "challenge")

    os.mkdir(path=ansible_challenge_directory)

    LOG.debug(msg=f"Directory {ansible_challenge_directory} created.")

    if template == Template.APACHE_PHP:
        track_template = env.get_template(
            name=os.path.join(Template.APACHE_PHP, "index.php.j2")
        )
        render = track_template.render(data={"name": name})
        with open(
            file=(p := os.path.join(ansible_challenge_directory, "index.php")),
            mode="w",
            encoding="utf-8",
        ) as f:
            f.write(render)

        LOG.debug(msg=f"Wrote {p}.")

    if template == Template.PYTHON_SERVICE:
        track_template = env.get_template(
            name=os.path.join(Template.PYTHON_SERVICE, "app.py.j2")
        )
        render = track_template.render(data={"name": name})
        with open(
            file=(p := os.path.join(ansible_challenge_directory, "app.py")),
            mode="w",
            encoding="utf-8",
        ) as f:
            f.write(render)

        LOG.debug(msg=f"Wrote {p}.")

        with open(
            file=(p := os.path.join(ansible_challenge_directory, "flag-1.txt")),
            mode="w",
            encoding="utf-8",
        ) as f:
            f.write(f"{{{{ track_flags.{name}_flag_1 }}}} (1/2)\n")

        LOG.debug(msg=f"Wrote {p}.")

    if template == Template.RUST_WEBSERVICE:
        # Copy the entire challenge template
        shutil.copytree(
            os.path.join(
                new_template_path,
                Template.RUST_WEBSERVICE,
                "source",
            ),
            ansible_challenge_directory,
            dirs_exist_ok=True,
        )
        LOG.debug(msg=f"Wrote files to {ansible_challenge_directory}")

        manifest_template = env.get_template(
            name=os.path.join(Template.RUST_WEBSERVICE, "Cargo.toml.j2")
        )
        render = manifest_template.render(data={"name": name})
        with open(
            file=(p := os.path.join(ansible_challenge_directory, "Cargo.toml")),
            mode="w",
            encoding="utf-8",
        ) as f:
            f.write(render)

        LOG.debug(msg=f"Wrote {p}.")
