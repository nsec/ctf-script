# CTF Script

## Usage

Setup a `CTF_ROOT_DIR` environment variable to make the script execute in the right folder or execute the script from that folder.

## Installation

Install with [uv](https://docs.astral.sh/uv/guides/tools/):

```bash
uv tool install git+https://github.com/nsec/ctf-script.git
```

Install with pipx:

```bash
pipx install git+https://github.com/nsec/ctf-script.git
```

### Add Bash/Zsh autocompletion to .bashrc

```bash
echo 'eval "$(register-python-argcomplete ctf)"' >> ~/.bashrc && source ~/.bashrc # If using bash
echo 'eval "$(register-python-argcomplete ctf)"' >> ~/.zshrc && source ~/.zshrc   # If using zsh
```

## Development

Install with [uv](https://docs.astral.sh/uv/guides/tools/) virtual environment:

```bash
git clone https://github.com/nsec/ctf-script.git
cd ctf-script
uv venv venv
source venv/bin/activate
uv pip install -e .
```

Install with virtual environment and pip:

```bash
git clone https://github.com/nsec/ctf-script.git
cd ctf-script
python3 -m venv venv
source venv/bin/activate
pip install -e .
```
