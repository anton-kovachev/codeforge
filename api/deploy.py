"""Build an AWS Lambda deployment package (zip) for the DebugForge server.

Mirrors the approach used in the super_twin backend: install dependencies for the
Lambda runtime using the official AWS Lambda Python Docker image, copy the application
files alongside them, and zip everything up for upload to Lambda.
"""

import os
import shutil
import subprocess
import zipfile

APP_FILES = [
    "server.py",
    "lambda_handler.py",
    "models.py",
    "bedrock_agent_client.py",
]


def main():
    print("Creating Lambda deployment package...")

    # Clean up (handle files created by Docker as root)
    if os.path.exists("lambda-package"):

        def _on_rmtree_error(func, path, exc_info):
            try:
                os.chmod(path, 0o700)
            except Exception:
                pass
            func(path)

        shutil.rmtree("lambda-package", onerror=_on_rmtree_error)
    if os.path.exists("lambda-deployment.zip"):
        os.remove("lambda-deployment.zip")

    # Create package directory
    os.makedirs("lambda-package")

    # Install dependencies using Docker with the Lambda runtime image, for compatibility
    print("Installing dependencies for Lambda runtime...")
    docker_cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{os.getcwd()}:/var/task",
        "--platform",
        "linux/amd64",
        "--entrypoint",
        "",
        "-u",
        f"{os.getuid()}:{os.getgid()}",
        "public.ecr.aws/lambda/python:3.12",
        "/bin/sh",
        "-c",
        "pip install --target /var/task/lambda-package -r /var/task/requirements.txt --timeout 240 --retries 5 --no-cache-dir --platform manylinux2014_x86_64 --only-binary=:all: --upgrade",
    ]
    subprocess.run(docker_cmd, check=True)

    # Copy application files
    print("Copying application files...")
    for file in APP_FILES:
        if os.path.exists(file):
            shutil.copy2(file, "lambda-package/")

    # Create zip
    print("Creating zip file...")
    with zipfile.ZipFile("lambda-deployment.zip", "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _dirs, files in os.walk("lambda-package"):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, "lambda-package")
                zipf.write(file_path, arcname)

    size_mb = os.path.getsize("lambda-deployment.zip") / (1024 * 1024)
    print(f"Created lambda-deployment.zip ({size_mb:.2f} MB)")


if __name__ == "__main__":
    main()
