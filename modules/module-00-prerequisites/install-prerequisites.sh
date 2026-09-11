#!/usr/bin/env bash
set -euo pipefail

# Install local prerequisites for the ShopSmart AgentCore course.
# This script installs or verifies local tooling only; it does not create AWS resources.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
VENV_DIR="${VENV_DIR:-$REPO_ROOT/.venv}"

log()  { printf '\n==> %s\n' "$*"; }
warn() { printf '\nWARNING: %s\n' "$*" >&2; }

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

install_macos() {
  log "Installing prerequisites for macOS"

  if ! command_exists brew; then
    log "Installing Homebrew"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    warn "If brew is not available in this shell, follow Homebrew's post-install instructions and rerun this script."
  fi

  brew install python@3.11 git jq unzip awscli 2>/dev/null || true

  if ! command_exists docker; then
    log "Installing Docker Desktop"
    brew install --cask docker
    warn "Start Docker Desktop, wait until it is running, then rerun this script."
  fi
}

install_debian_ubuntu() {
  log "Installing prerequisites for Debian/Ubuntu"

  sudo apt-get update
  sudo apt-get install -y \
    ca-certificates curl git jq unzip \
    python3 python3-venv python3-pip \
    docker.io

  sudo systemctl enable docker
  sudo systemctl start docker

  if ! id -nG "$USER" | grep -qw docker; then
    sudo usermod -aG docker "$USER"
    warn "Your user was added to the docker group. Log out and back in, or run 'newgrp docker', before using Docker without sudo."
  fi
}

install_rhel_amazon() {
  log "Installing prerequisites for RHEL/Amazon Linux"

  local package_manager="yum"
  if command_exists dnf; then
    package_manager="dnf"
  fi

  sudo "$package_manager" install -y \
    ca-certificates curl git jq unzip \
    python3 python3-pip \
    docker

  sudo systemctl enable docker
  sudo systemctl start docker

  if ! id -nG "$USER" | grep -qw docker; then
    sudo usermod -aG docker "$USER"
    warn "Your user was added to the docker group. Log out and back in, or run 'newgrp docker', before using Docker without sudo."
  fi
}

install_aws_cli_linux() {
  if command_exists aws; then
    return
  fi

  log "Installing AWS CLI v2"
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' RETURN

  curl -fsSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip \
    -o "$tmp_dir/awscliv2.zip"
  unzip -q "$tmp_dir/awscliv2.zip" -d "$tmp_dir"
  sudo "$tmp_dir/aws/install" --update
}

install_python_environment() {
  log "Creating the Python virtual environment"
  python3 -m venv "$VENV_DIR"

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  python -m pip install --upgrade pip

  if [[ -f "$REPO_ROOT/requirements.txt" ]]; then
    log "Installing course Python dependencies"
    python -m pip install -r "$REPO_ROOT/requirements.txt"
  fi

  if [[ -f "$REPO_ROOT/aria-agent/requirements.txt" ]]; then
    log "Installing agent and Browser development dependencies"
    python -m pip install -r "$REPO_ROOT/aria-agent/requirements.txt"
  fi

  log "Installing AgentCore CLI"
  python -m pip install amazon-bedrock-agentcore-cli
}

verify_installation() {
  log "Verifying local tools"

  local failed=0
  for command_name in python3 aws docker git curl unzip; do
    if command_exists "$command_name"; then
      printf 'OK  %-10s %s\n' "$command_name" "$(command -v "$command_name")"
    else
      printf 'FAIL %-10s not found\n' "$command_name"
      failed=1
    fi
  done

  # The venv contains the Python packages and AgentCore CLI.
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  for command_name in python pip streamlit agentcore; do
    if command_exists "$command_name"; then
      printf 'OK  %-10s %s\n' "$command_name" "$(command -v "$command_name")"
    else
      printf 'FAIL %-10s not found in %s\n' "$command_name" "$VENV_DIR"
      failed=1
    fi
  done

  if docker info >/dev/null 2>&1; then
    printf 'OK  %-10s daemon is running\n' docker
  else
    warn "Docker is installed but the daemon is not reachable. Start Docker Desktop or the Docker service, then rerun the verification commands."
  fi

  if (( failed )); then
    return 1
  fi
}

main() {
  log "ShopSmart AgentCore course prerequisite installer"
  printf 'Repository: %s\n' "$REPO_ROOT"
  printf 'Virtual environment: %s\n' "$VENV_DIR"

  local os_name
  os_name="$(uname -s)"

  case "$os_name" in
    Darwin)
      install_macos
      ;;
    Linux)
      if [[ ! -f /etc/os-release ]]; then
        echo "Cannot determine the Linux distribution." >&2
        exit 1
      fi
      # shellcheck disable=SC1091
      source /etc/os-release
      case "${ID:-}" in
        ubuntu|debian)
          install_debian_ubuntu
          install_aws_cli_linux
          ;;
        amzn|rhel|centos|fedora)
          install_rhel_amazon
          install_aws_cli_linux
          ;;
        *)
          echo "Unsupported Linux distribution: ${ID:-unknown}" >&2
          echo "Install Python 3.11, AWS CLI v2, Docker, Git, curl, unzip, and jq manually, then rerun this script." >&2
          exit 1
          ;;
      esac
      ;;
    *)
      echo "Unsupported operating system: $os_name" >&2
      echo "Windows users should run this script from WSL2 Ubuntu or install the tools manually." >&2
      exit 1
      ;;
  esac

  install_python_environment
  verify_installation

  log "Installation complete"
  cat <<EOF
Activate the environment in every new terminal:

  source "$VENV_DIR/bin/activate"

Configure AWS credentials next:

  aws configure
  aws sts get-caller-identity

For ARM64 AgentCore Runtime builds from an x86_64 machine, register emulation
before building a container:

  docker run --privileged --rm tonistiigi/binfmt --install arm64
EOF
}

main "$@"
