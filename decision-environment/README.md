# Decision Environment (EDA)

This folder defines a Decision Environment (DE) image for Event-Driven Ansible using ansible-builder.

## Contents
- execution-environment.yml: build recipe (base image, package manager, dependency files)
- requirements.yml: Ansible collections to include (e.g., ansible.eda)
- requirements.txt: Python packages to include (e.g., aiomqtt)

## Prerequisites
- Podman or Docker
- Python 3 and ansible-builder installed:
  ```bash
  pip install ansible-builder
  ```

## Build the image
Option A (from repo root):
```bash
ansible-builder build \
  -t hue-de:latest \
  -f decision-environment/execution-environment.yml \
  --context decision-environment
```

Option B (from this folder):
```bash
cd decision-environment
ansible-builder build -t hue-de:latest
```

### Build with latest Galaxy collections (recommended)

Before building a new DE, publish your updated collection (e.g., `ipvsean.hue_booth_demo`) to Galaxy so the build can fetch the latest version.

Then force a fresh base pull and no cache:

```bash
cd decision-environment
ansible-builder build -t localhost/hue-de:latest --extra-build-cli-args='--no-cache --pull'
```

Notes:
- The base image is registry.redhat.io/ansible-automation-platform-25/de-supported-rhel8:latest.
- The build uses microdnf and installs system packages listed in execution-environment.yml.

## Run a quick check
Print Python and collections inside the image:
```bash
podman run --rm hue-de:latest python -V
podman run --rm hue-de:latest ansible-galaxy collection list | cat
```

Run ansible-rulebook using the image (mount the repo to access rulebooks/plugins):
```bash
podman run --rm -it \
  -v $(pwd):/workspace \
  -w /workspace \
  localhost/hue-de:latest \
  ansible-rulebook -r extensions/eda/rulebooks/rulebook.yml -S . --print-events
```

## Push to a registry (optional)
```bash
podman tag hue-de:latest <registry>/<namespace>/hue-de:latest
podman push <registry>/<namespace>/hue-de:latest
```

for example:

```bash
podman tag hue-de:latest quay.io/acme_corp/hue-de:latest
podman push quay.io/acme_corp/hue-de:latest
```
