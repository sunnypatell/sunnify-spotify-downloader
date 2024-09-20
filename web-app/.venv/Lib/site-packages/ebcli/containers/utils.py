import subprocess

def is_docker_compose_installed():
    try:
        subprocess.run(['docker','compose','version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False
