#!/usr/bin/env python3
import paramiko
import os

REMOTE = os.environ["REMOTE_ADDRESS"]
BRANCH = os.environ["BRANCH_NAME"]

PRIVATE_KEY_PATH = "key"
REMOTE_DEPLOY_KEY = "/root/.ssh/github/git_deploy"

def run_remote(ssh, cmd):
    stdin, stdout, stderr = ssh.exec_command(cmd)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()

    if out:
        print("[REMOTE]", out)
    if err:
        print("[REMOTE STDERR]", err)

    return stdout.channel.recv_exit_status()

def load_private_key():
    """Load RSA or ED25519."""
    try:
        return paramiko.RSAKey.from_private_key_file(PRIVATE_KEY_PATH)
    except paramiko.ssh_exception.SSHException:
        return paramiko.Ed25519Key.from_private_key_file(PRIVATE_KEY_PATH)

def main():
    print("Connecting to remote:", REMOTE)

    # 1. Connect SSH
    pkey = load_private_key()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(REMOTE, username="root", pkey=pkey)

    print("=== Connected to remote ===")

    # 2. Write SSH config for GitHub
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
    print("Ensuring koldavar repo exists...")
    run_remote(ssh, "test -d koldavar || git clone git@github.com:omriwa/koldavar.git")

    # 4. Fetch and reset to origin
    print("Fetching latest...")
    run_remote(ssh, f"cd koldavar && git fetch origin")

    print(f"Checking out and resetting branch: {BRANCH}")
    run_remote(
        ssh,
        f"cd koldavar && "
        f"git checkout -B {BRANCH} origin/{BRANCH} && "
        f"git reset --hard origin/{BRANCH}"
    )

    # 5. Apply to Kubernetes
    print("Applying Kubernetes manifests...")
    run_remote(ssh, "cd koldavar && kubectl apply -k ./k8s/base")

    print("=== Deployment complete ===")
    ssh.close()

if __name__ == "__main__":
    main()
