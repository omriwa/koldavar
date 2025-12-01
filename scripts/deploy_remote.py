#!/usr/bin/env python3
import paramiko
import os

REMOTE = os.environ["REMOTE_ADDRESS"]
BRANCH = os.environ["BRANCH_NAME"]

# The SSH key used to connect to the server
PRIVATE_KEY_PATH = "key"

# Existing deploy key on remote
REMOTE_DEPLOY_KEY = "/root/.ssh/github/github_deploy"


def run_remote(ssh, command):
    stdin, stdout, stderr = ssh.exec_command(command)
    out = stdout.read().decode()
    err = stderr.read().decode()

    if out.strip():
        print("[REMOTE]", out.strip())
    if err.strip():
        print("[REMOTE STDERR]", err.strip())

    return stdout.channel.recv_exit_status()


def load_private_key():
    """Load RSA or ED25519."""
    try:
        return paramiko.RSAKey.from_private_key_file(PRIVATE_KEY_PATH)
    except paramiko.ssh_exception.SSHException:
        return paramiko.Ed25519Key.from_private_key_file(PRIVATE_KEY_PATH)


def main():
    print("Connecting to remote:", REMOTE)

    # 1. Connect to remote
    pkey = load_private_key()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(REMOTE, username="root", pkey=pkey)

    print("=== Connected to remote ===")

    # 2. Ensure SSH config points to existing deploy key
    print("Configuring SSH for GitHub...")

    ssh_config = f"""Host github.com
    HostName github.com
    User git
    IdentityFile {REMOTE_DEPLOY_KEY}
    IdentitiesOnly yes
    """

    run_remote(
        ssh,
        f"echo \"{ssh_config}\" > /root/.ssh/config && chmod 600 /root/.ssh/config"
    )

    # 3. Ensure repo exists
    print("Ensuring repository exists...")
    run_remote(
        ssh,
        "test -d koldavar || git clone git@github.com:omriwa/koldavar.git"
    )

    # 4. Fetch changes
    print("Fetching latest changes...")
    run_remote(
        ssh,
        "cd koldavar && git fetch origin"
    )

    # 5. Checkout branch
    print(f"Checking out branch: {BRANCH}")
    run_remote(
        ssh,
        f"cd koldavar && git checkout {BRANCH} "
        f"|| git checkout -b {BRANCH} origin/{BRANCH}"
    )

    # 6. Apply Kubernetes manifests
    print("Applying Kubernetes manifests...")
    run_remote(
        ssh,
        "cd koldavar && kubectl apply -k ./k8s/base"
    )

    print("=== Deployment complete ===")
    ssh.close()


if __name__ == "__main__":
    main()
