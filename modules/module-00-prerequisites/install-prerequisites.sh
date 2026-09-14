#!/usr/bin/env bash
set -euo pipefail

# Install local prerequisites for the ShopSmart AgentCore course.
# This script installs or verifies local tooling only; it does not create AWS resources.
# Completed steps are recorded so a rerun resumes after the last failed step.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/../.." && pwd)"
VENV_DIR="${VENV_DIR:-$REPO_ROOT/.venv}"
INSTALL_STATE_FILE="${INSTALL_STATE_FILE:-$REPO_ROOT/.prerequisites-install-state}"

log()  { printf '\n==> %s\n' "$*"; }
warn() { printf '\nWARNING: %s\n' "$*" >&2; }

if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
  GREEN=$'\033[0;32m'
  RESET=$'\033[0m'
else
  GREEN=''
  RESET=''
fi

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

step_done() {
  [[ -f "$INSTALL_STATE_FILE" ]] && grep -Fqx -- "$1" "$INSTALL_STATE_FILE"
}

mark_step_done() {
  mkdir -p "$(dirname -- "$INSTALL_STATE_FILE")"
  printf '%s\n' "$1" >> "$INSTALL_STATE_FILE"
}

run_step() {
  local step_name="$1"
  shift

  if step_done "$step_name"; then
    log "Skipping completed step: $step_name"
    return 0
  fi

  log "Running step: $step_name"
  if "$@"; then
    mark_step_done "$step_name"
    return 0
  fi

  warn "Step failed: $step_name"
  warn "Rerun this script to retry from this step. Completed steps will be skipped."
  return 1
}

install_homebrew() {
  if command_exists brew; then
    return 0
  fi

  log "Installing Homebrew"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" || return 1
  warn "If brew is not available in this shell, follow Homebrew's post-install instructions and rerun this script."
}

install_macos_packages() {
  brew install python@3.11 git jq unzip awscli
}

install_macos_docker() {
  if command_exists docker; then
    return 0
  fi

  log "Installing Docker Desktop"
  brew install --cask docker
  warn "Start Docker Desktop, wait until it is running, then rerun this script."
}

install_macos() {
  log "Installing prerequisites for macOS"
  run_step "macos-homebrew" install_homebrew || return 1
  run_step "macos-packages" install_macos_packages || return 1
  run_step "macos-docker" install_macos_docker
}

install_debian_packages() {
  sudo apt-get update || return 1
  sudo apt-get install -y \
    ca-certificates curl git jq unzip \
    python3 python3-venv python3-pip \
    docker.io
}

start_debian_docker() {
  sudo systemctl enable docker || return 1
  sudo systemctl start docker
}

configure_linux_docker_group() {
  if id -nG "$USER" | grep -qw docker; then
    return 0
  fi

  sudo usermod -aG docker "$USER" || return 1
  warn "Your user was added to the docker group. Log out and back in, or run 'newgrp docker', before using Docker without sudo."
}

install_debian_ubuntu() {
  log "Installing prerequisites for Debian/Ubuntu"
  run_step "debian-packages" install_debian_packages || return 1
  run_step "debian-docker-service" start_debian_docker || return 1
  run_step "debian-docker-group" configure_linux_docker_group
}

install_rhel_packages() {
  local package_manager="yum"
  if command_exists dnf; then
    package_manager="dnf"
  fi

  sudo "$package_manager" install -y \
    ca-certificates curl git jq unzip \
    python3 python3-pip \
    docker
}

start_rhel_docker() {
  sudo systemctl enable docker || return 1
  sudo systemctl start docker
}

install_rhel_amazon() {
  log "Installing prerequisites for RHEL/Amazon Linux"
  run_step "rhel-packages" install_rhel_packages || return 1
  run_step "rhel-docker-service" start_rhel_docker || return 1
  run_step "rhel-docker-group" configure_linux_docker_group
}

install_aws_cli_linux() {
  if command_exists aws; then
    return 0
  fi

  log "Installing AWS CLI v2"
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "$tmp_dir"' RETURN

  curl -fsSL https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip \
    -o "$tmp_dir/awscliv2.zip" || return 1
  unzip -q "$tmp_dir/awscliv2.zip" -d "$tmp_dir" || return 1
  sudo "$tmp_dir/aws/install" --update
}

create_python_environment() {
  python3 -m venv "$VENV_DIR"
}

upgrade_pip() {
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  python -m pip install --upgrade pip
}

install_root_dependencies() {
  [[ -f "$REPO_ROOT/requirements.txt" ]] || return 0

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  log "Installing course Python dependencies"
  python -m pip install -r "$REPO_ROOT/requirements.txt"
}

install_python_environment() {
  log "Setting up the Python virtual environment"
  run_step "python-venv" create_python_environment || return 1
  run_step "python-pip" upgrade_pip || return 1
  run_step "python-root-dependencies" install_root_dependencies
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

  if [[ ! -d "$VENV_DIR" ]]; then
    warn "Python virtual environment not found at $VENV_DIR"
    return 1
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  for command_name in python pip streamlit; do
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
  if [[ "${1:-}" == "--reset" ]]; then
    rm -f "$INSTALL_STATE_FILE"
    shift
    log "Removed installer state; all steps will run again."
  fi

  if [[ $# -gt 0 ]]; then
    echo "Usage: $0 [--reset]" >&2
    exit 2
  fi

  log "ShopSmart AgentCore course prerequisite installer"
  printf 'Repository: %s\n' "$REPO_ROOT"
  printf 'Virtual environment: %s\n' "$VENV_DIR"
  printf 'State file: %s\n' "$INSTALL_STATE_FILE"

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
          ;;
        amzn|rhel|centos|fedora)
          install_rhel_amazon
          ;;
        *)
          echo "Unsupported Linux distribution: ${ID:-unknown}" >&2
          echo "Install Python 3.11, AWS CLI v2, Docker, Git, curl, unzip, and jq manually, then rerun the script." >&2
          exit 1
          ;;
      esac
      run_step "aws-cli" install_aws_cli_linux
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
  printf '%b\n' "${GREEN}Next steps:${RESET}"
  printf '%b\n' "${GREEN}1. Activate the environment in every new terminal:${RESET}"
  printf '   source "%s/bin/activate"\n\n' "$VENV_DIR"
  printf '%b\n' "${GREEN}2. Configure AWS credentials:${RESET}"
  printf '   aws configure\n'
  printf '   aws sts get-caller-identity\n\n'
  printf '%b\n' "${GREEN}3. For ARM64 AgentCore Runtime builds from an x86_64 machine, register emulation before building a container:${RESET}"
  printf '   docker run --privileged --rm tonistiigi/binfmt --install arm64\n'
}

main "$@"
