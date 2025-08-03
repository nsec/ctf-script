# CTF Name CHANGEME

This repository was generated using the [`ctf-script` tool](https://github.com/nsec/ctf-script). To contribute, install it first.

There are two main ways to do development: With a **local environment** or by using **GitHub codespaces**. Both are documented below.

## Tutorial: set up your local environment

This tutorial was written and tested on Windows using WSL (Ubuntu 24.04).

### 0. Install dependencies

```bash
sudo apt update
sudo apt install python3-pip pipx
pipx ensurepath
```

Close and re-open your terminal.

#### 0.1 Configure WSL

Make sure WSL defaults to version 2:

```bash
wsl --set-default-version 2
```

Check if `systemd` is enabled for WSL2:

```bash
systemctl  # press Q to exit
```

If it says systemd is not enabled, enable systemd for WSL2:

```bash
echo "[boot]
systemd=true" | sudo tee -a /etc/wsl.conf
```

Reboot wsl.

```bash
# IMPORTANT: Make sure to close any VS Code window that is currently open BEFORE running this command.
wsl.exe --shutdown
```

Re-open a WSL shell.

#### 0.2 Ansible

```bash
pipx install --include-deps ansible
pipx inject ansible passlib
ansible --help  # This command MUST work
```

#### 0.3 Incus

Install incus

```bash
sudo apt install --no-install-recommends --yes zfsutils-linux
curl https://pkgs.zabbly.com/get/incus-stable | sudo sh
sudo adduser $USER incus-admin
incus --help  # This command MUST work
```

Reboot WSL to make sure the incus server properly installs.

```bash
wsl.exe --shutdown
```

Re-open a WSL shell.

Initialize Incus

```bash
incus admin init --minimal  # This command has no output.
incus version  # You MUST see the Server version in this output
```

##### Incus and Docker

If you have Docker and Incus installed, there might be networking issues. This is documented here: [https://linuxcontainers.org/incus/docs/main/howto/network_bridge_firewalld/#prevent-connectivity-issues-with-incus-and-docker](https://linuxcontainers.org/incus/docs/main/howto/network_bridge_firewalld/#prevent-connectivity-issues-with-incus-and-docker)

You need to enable IPv4 forwarding.

```bash
echo "net.ipv4.conf.all.forwarding=1" > /etc/sysctl.d/99-forwarding.conf
systemctl restart systemd-sysctl
```
##### Non-debian OS and User Namespace

Read this section only if you're on non-debian OS. Incus uses user namespaces to run unprivileged containers. To do so, it checks for subuid and subgid of the root ([Incus Idmaps for user namespace](https://linuxcontainers.org/incus/docs/main/userns-idmap/)).

However, these may not be defined depending on the OS. The fix is simple, but it may vary from OS to OS. Please read [Incus installation document](https://linuxcontainers.org/incus/docs/main/installing/) and your OS documentation on Incus.

Here's an example for Archlinux: `usermod -v 1000000-1000999999 -w 1000000-1000999999 root`, source: [https://wiki.archlinux.org/title/Incus#Unprivileged_containers](https://wiki.archlinux.org/title/Incus#Unprivileged_containers)

#### 0.4 OpenTofu (open-source Terraform fork)

```bash
curl -sL https://get.opentofu.org/install-opentofu.sh -o install-opentofu.sh
chmod +x install-opentofu.sh
./install-opentofu.sh --install-method deb
rm -f install-opentofu.sh
tofu --help  # This command MUST work
```

#### 0.5 Git LFS

Install [Git LFS](https://github.com/git-lfs/git-lfs#installing). With a Debian-based or RHEL-based distro, you can install it with the [package repository](https://github.com/git-lfs/git-lfs/blob/main/INSTALLING.md#2-installing-packages) with:

```bash
# Debian/Ubuntu
sudo apt-get install git-lfs

# RHEL
sudo yum install git-lfs
```

### 1. Privately fork the repository in your account

[https://github.com/CHANGEME/ctf/fork](https://github.com/CHANGEME/ctf/fork)

### 2. Clone your fork

```bash
git clone https://github.com/<your_username>/ctf.git
cd ctf
```

### 3. Create a branch

```bash
git checkout -b my_awesome_challenge
```

### 4. Open the repo directory in VS Code

When you open the directory, there should be a popup asking if you trust the authors. Press Yes, then you should
have a notification to install recommended extensions. Install them.
This will set up the YAML extension with JSON schemas, which provides autocomplete, error highlighting and
documentation for some of the YAML files used in the CTF, like `track.yaml`.

### 5. Install the python package

See [installation instructions](https://github.com/nsec/ctf-script).

This will allow to use the `ctf` command.

### 6. Add Bash/Zsh autocompletion to .bashrc

```bash
echo 'eval "$(register-python-argcomplete ctf)"' >> ~/.bashrc && source ~/.bashrc # If using bash
echo 'eval "$(register-python-argcomplete ctf)"' >> ~/.zshrc && source ~/.zshrc   # If using zsh
```

### 7. Use the `ctf new` command

This will create a new directory `./challenges/myawesometrack` with boilerplate files in it.

```bash
ctf new --name myawesometrack
```

### 8. Deploy the challenge locally

```bash
ctf deploy --track myawesometrack
```

If you have an error here regarding storage pool, create a default incus storage pool:

```bash
incus storage create default dir
```

And run the `ctf deploy --track myawesometrack` command again.

Once done, you should have a container running that runs an apache PHP server that you can reach at the IP provided in the output!

### 9. Test everything works and CURL the flag

```bash
curl http://<IPOfTheMachine>
```

In track.yaml, a `dev_port_mapping` has also been set to map `main-site`'s port 80 to your machine's `localhost:800`. Make sure it works.

```bash
curl http://localhost:800
```

Expected output in both:

```html
Hello world!
<!-- FLAG-CHANGE_ME -->
```

### Final details

You now have everything to build the rest of your challenge locally and deploy it in a way that will work in production.
When you open a PR in the main repository, static validations will run automatically AND a full deployment will be done
automatically to find any problem in the deployment.

Navigate in the newly created `challenges/[trackname]` to see the created files.
They all have comments to explain their purpose and what each config means.

When you want to do deploy changes to your challenge with terraform + ansible,
simply run this command again after making changes:

```bash
ctf deploy --tracks myawesometrack
```

If you need to destroy your track to deploy from scratch, simply use the `ctf destroy` command. This will destroy everything created by Terraform:

```bash
ctf destroy
```

## Tutorial: Set up a **GitHub Codespace environment**

### 1. Follow steps 1 to 4 from [Tutorial: set up your local environment](#1-privately-fork-the-repository-in-your-account)

If you are not sure, **you should install the recommended extensions**.

### 2. Sign in to GitHub

a. `CTRL` + `Shift` + `P` ==> "Codespaces: Connect to codespace..."
b. Follow the instructions in the browser to connect to GitHub and authorize the app.

### 3. Create the codespace

a. `CTRL` + `Shift` + `P` ==> "Codespaces: Connect to codespace...". You should get a message saying there are no codespace. Click the "create" button.

b. Choose your private fork (Ex. `Res260/ctf-2025`). Choose your work branch (`my_awesome_challenge` in this case). Choose either the 2 core or the 4 cores machine. GitHub offers 120 core hours per month, so 60 hours of work for the 2 core machine and 30 hours for the 4 cores machine.

c. The first connection might fail with a "not found" error. If this happens, just do a. again.

d. Wait a minute or two for the initial setup of the codespace.

### 4. Install the recommended extensions

When the codespace opens (you know it works by seeing `Codespaces: [somename]` on the bottom left of VS Code), you should be prompted to install the recommended extensions. Install them.

### 5. Setup the codespace

a. Open a terminal (Terminal --> New Terminal)

b.

```bash
./setup-codespace
```

It will take about 1 minute with the 2 cores machine.

### 6. Follow steps 6. 7. 8. and Final Details from [Tutorial: set up your local environment](#7-use-the-ctf-new-command)

## The `files` Folder

### Add a file to download

When your challenge needs a file to download, you must add your file to your track's `files` folder (e.g. `challenges/my-awesome-track/files/my-awesome-file.pcap`).

### If using [askgod](https://github.com/nsec/askgod): Add an Image or Sound to Your Flag

If you want your flag to trigger a sound or an image during the competition, you need to do the following:

1. Add a new tag to your flag in `challenges/my-awesome-track/track.yaml`. The tags must match the name of the file that you will be adding in `challenges/my-awesome-track/files/askgod/(sounds|gifs)/` or `challenges/ctf/files/askgod/(sounds|gifs)/`.

```yaml
flags:
  - flag: FLAG-CHANGE-ME
    value: 10
    description: CHANGE-ME
    return_string: CHANGE-ME"
    tags:
      discourse: change_me
      # The tags to be added are the ones below
      ui_sound: my-awesome-sound.mp3
      ui_gif: my-awesome-gif.gif
```

2. If you are choosing to use a custom sound and not defaults ones in the `ctf` track folder, you must add them in `challenges/my-awesome-track/files/askgod/(sounds|gifs)/`. Example: `challenges/my-awesome-track/files/askgod/sounds/my-awesome-sound.mp3`.