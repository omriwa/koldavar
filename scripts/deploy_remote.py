#!/usr/bin/env python3
import paramiko
import os
import sys

REMOTE = os.environ["REMOTE_ADDRESS"]
BRANCH = os.environ["BRANCH_NAME"]

PRIVATE_KEY_PATH = "key"
REMOTE_DEPLOY_KEY = "/root/.ssh/github/git_deploy"

def run_remote(ssh, command, fail_on_error=True):
    stdin, stdout, stderr = ssh.exec_command(command)
    exit_code = stdout.channel.recv_exit_status()

    out = stdout.read().decode()
    err = stderr.read().decode()

    if out.strip():
        print("[REMOTE]", out.strip())
    if err.strip():
        print("[REMOTE STDERR]", err.strip())

    if fail_on_error and exit_code != 0:
        print(f"[ERROR] Remote command failed: {command}")
        print(f"[ERROR] Exit code: {exit_code}")
        sys.exit(exit_code)

    return exit_code

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

    # 2. Configure GitHub SSH key
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

    # 4. Fetch + reset to correct branch
    print("Fetching latest...")
    run_remote(ssh, f"cd koldavar && git fetch origin")

    print(f"Checking out and resetting branch: {BRANCH}")
    run_remote(
        ssh,
        f"cd koldavar && "
        f"git checkout -B {BRANCH} origin/{BRANCH} && "
        f"git reset --hard origin/{BRANCH}"
    )

    # 5. Deployment mode selection
    print("Determining deployment mode...")

    IS_MERGE = BRANCH in ["main", "master", "prod", "production"]

    if IS_MERGE:
        print(">>> Merge detected – using HELM UPGRADE <<<")
        deploy_cmd = (
            "cd koldavar/k8s && "
            "helm upgrade --install koldavar ./helm/koldavar "
            "--namespace default --create-namespace"
        )
    else:
        print(">>> Non-merge – applying helm template via kubectl <<<")
        deploy_cmd = (
            "cd koldavar/k8s && "
            "helm template koldavar ./helm/koldavar | kubectl apply -f -"
        )

    # 6. Execute deployment
    run_remote(ssh, deploy_cmd, fail_on_error=True)

    # 7. Dependencies (Traefik CRDs)
    print("Installing Traefik CRDs…")
    run_remote(
        ssh,
        "kubectl apply -f https://raw.githubusercontent.com/traefik/traefik/v2.10/docs/content/reference/dynamic-configuration/kubernetes-crd-definition-v1.yml"
    )

    print("=== Deployment complete ===")
    ssh.close()

if __name__ == "__main__":
    main()
