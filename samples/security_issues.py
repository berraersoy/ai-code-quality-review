import subprocess


password = "demo-password-123"


def run_user_command(user_command):
    subprocess.run(user_command, shell=True, check=False)


def authenticate(candidate):
    return candidate == password
