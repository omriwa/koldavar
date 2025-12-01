#!/usr/bin/env python3
import paramiko
import os

REMOTE = os.environ["REMOTE_ADDRESS"]
BRANCH = os.environ["BRANCH_NAME"]

# The deploy key created in GitHub Actions as a secret
LOCAL_DEPLOY_KEY = "deploy_key"
REMOTE_DEPLOY_KEY = ".ssh/github_deploy"

PRIVATE_KEY_PATH = "key"  # The private SSH key used to connect to the server

def run_remote(ssh, command):
    stdin, stdout, stderr = ssh.exec_command(command)
    out = stdout.read().decode()
    err = stderr.read().decode()

    if out.strip():
        print(out.strip())
    if err.strip():
        print("STDERR:", err.strip())

    return stdout.channel.recv_exit_status()

def main():
    print("Connecting to remote:", REMOTE)

    # Connect to server using private key
    # Auto-detect key type
    try:
        pkey = paramiko.RSAKey.from_private_key_file(PRIVATE_KEY_PATH)
    except paramiko.ssh_exception.SSHException:
        try:
            pkey = paramiko.Ed25519Key.from_private_key_file(PRIVATE_KEY_PATH)
        except:
            raise
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(REMOTE, username="root", pkey=pkey)

    print("=== Connected ===")

    # --- 1. Upload GitHub deploy key ---
    print("Uploading GitHub deploy key to remote...")

    # Create .ssh directory if missing
    run_remote(ssh, "mkdir -p /root/.ssh && chmod 700 /root/.ssh")

    sftp = ssh.open_sftp()
    sftp.put(LOCAL_DEPLOY_KEY, REMOTE_DEPLOY_KEY)
    sftp.chmod(REMOTE_DEPLOY_KEY, 0o600)
    sftp.close()

    print("Deploy key uploaded to:", REMOTE_DEPLOY_KEY)

    # --- 2. Write SSH config ---
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

    # --- 3. Clone repo if missing ---
    print("Cloning repository if missing...")
    run_remote(ssh, "test -d koldavar || git clone git@github.com:omriwa/koldavar.git")

    # --- 4. Fetch latest ---
    print("Fetching latest...")
    run_remote(ssh, "cd koldavar && git fetch origin")

    # --- 5. Checkout branch ---
    print("Checking out branch:", BRANCH)
    run_remote(
        ssh,
        f"cd koldavar && git checkout {BRANCH} || git checkout -b {BRANCH} origin/{BRANCH}"
    )

    # --- 6. Deploy ---
    print("Applying Kubernetes manifests...")
    run_remote(ssh, "cd koldavar && kubectl apply -k ./k8s/base")

    print("=== Deployment Complete ===")
    ssh.close()


if __name__ == "__main__":
    main()
