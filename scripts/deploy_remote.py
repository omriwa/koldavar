#!/usr/bin/env python3
import paramiko
import os
import sys

REMOTE = os.environ["REMOTE_ADDRESS"]
BRANCH = os.environ["BRANCH_NAME"]
PRIVATE_KEY_PATH = "key"  # created earlier in the workflow

def run_remote(ssh, command):
    stdin, stdout, stderr = ssh.exec_command(command)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip():
        print(out.strip())
    if err.strip():
        print("ERR:", err.strip())
    return stdout.channel.recv_exit_status()

def main():
    print("Connecting to remote server:", REMOTE)
    
    pkey = paramiko.RSAKey.from_private_key_file(PRIVATE_KEY_PATH)
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(REMOTE, username="root", pkey=pkey)

    print("=== Connected ===")

    # Ensure .ssh directory exists
    run_remote(ssh, "mkdir -p /root/.ssh && chmod 700 /root/.ssh")

    print("Writing SSH config for GitHub...")
    ssh_config = """Host github.com
    HostName github.com
    User git
    IdentityFile /root/.ssh/github_deploy
    IdentitiesOnly yes
    """

    run_remote(ssh, f"echo \"{ssh_config}\" > /root/.ssh/config && chmod 600 /root/.ssh/config")

    print("Cloning or updating repo...")
    run_remote(ssh, "test -d koldavar || git clone git@github.com:omriwa/koldavar.git")

    print("Fetching latest...")
    run_remote(ssh, "cd koldavar && git fetch origin")

    print("Checking out branch:", BRANCH)
    run_remote(
        ssh,
        f"cd koldavar && "
        f"git checkout {BRANCH} || git checkout -b {BRANCH} origin/{BRANCH}"
    )

    print("Applying Kubernetes manifests...")
    run_remote(ssh, "cd koldavar && kubectl apply -k ./k8s/base")

    print("=== Deployment Complete ===")

    ssh.close()


if __name__ == "__main__":
    main()
