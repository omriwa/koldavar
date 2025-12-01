#!/usr/bin/env python3
import paramiko
import os
import sys

REMOTE = os.environ["REMOTE_ADDRESS"]
BRANCH = os.environ["BRANCH_NAME"]
PRIVATE_KEY_PATH = "key"  # created earlier during workflow


def load_private_key(path: str):
    """Automatically load correct key type: RSA, ED25519, or ECDSA."""
    key_types = [
        paramiko.RSAKey,
        paramiko.Ed25519Key,
        paramiko.ECDSAKey,
    ]
    for key_cls in key_types:
        try:
            return key_cls.from_private_key_file(path)
        except Exception:
            continue
    raise Exception("❌ ERROR: Unsupported or invalid SSH private key format.")


def run_remote(ssh, command):
    """Run a remote command and print output."""
    print(f"\n[REMOTE] $ {command}")
    stdin, stdout, stderr = ssh.exec_command(command)

    out = stdout.read().decode()
    err = stderr.read().decode()

    if out.strip():
        print(out.strip())
    if err.strip():
        print("STDERR:", err.strip())

    return stdout.channel.recv_exit_status()


def main():
    print(f"Connecting to remote server: {REMOTE}")

    # Load key (auto-detect type)
    pkey = load_private_key(PRIVATE_KEY_PATH)

    # Connect
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(REMOTE, username="root", pkey=pkey)
    print("=== Connected ===")

    # Ensure SSH folder exists
    run_remote(ssh, "mkdir -p /root/.ssh && chmod 700 /root/.ssh")

    # Write GitHub SSH config
    print("Writing GitHub SSH config...")
    ssh_config = """Host github.com
    HostName github.com
    User git
    IdentityFile /root/.ssh/github_deploy
    IdentitiesOnly yes
"""

    run_remote(
        ssh,
        f"echo \"{ssh_config}\" > /root/.ssh/config && chmod 600 /root/.ssh/config"
    )

    # Clone repo if missing
    print("Cloning or updating repo...")
    run_remote(ssh, "test -d koldavar || git clone git@github.com:omriwa/koldavar.git")

    # Fetch
    print("Fetching latest changes...")
    run_remote(ssh, "cd koldavar && git fetch origin")

    # Checkout branch
    print(f"Checking out branch: {BRANCH}")
    run_remote(
        ssh,
        f"cd koldavar && "
        f"git checkout {BRANCH} || git checkout -b {BRANCH} origin/{BRANCH}"
    )

    # Apply K8s manifests
    print("Applying Kubernetes manifests...")
    run_remote(ssh, "cd koldavar && kubectl apply -k ./k8s/base")

    print("\n=== Deployment Complete ===")

    ssh.close()


if __name__ == "__main__":
    main()
