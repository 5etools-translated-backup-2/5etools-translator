# This scrips expects a GITHUB TOKEN
# It will create all repositories for translations + deployments

# TODO
# Create SSH keys

import requests
import time
from base64 import b64encode
from nacl import encoding, public
import os
from dotenv import load_dotenv

load_dotenv()
TRANSLATOR_GITHUB_TOKEN = os.getenv(
    "TRANSLATOR_GITHUB_TOKEN",
)
TRANSLATOR_GITHUB_USERNAME = os.getenv(
    "TRANSLATOR_GITHUB_USERNAME",
)
TRANSLATOR_GITHUB_REPO = "5etools-translator"
DEPLOYER_GITHUB_TOKEN = os.getenv(
    "DEPLOYER_GITHUB_TOKEN",
)
DEPLOYER_GITHUB_USERNAME = os.getenv(
    "DEPLOYER_GITHUB_USERNAME",
)

GITHUB_API_VERSION = "2022-11-28"
BACKUP_GITHUB_USERNAME = os.getenv(
    "BACKUP_GITHUB_USERNAME",
)
BACKUP_GITHUB_TRANSLATOR_REPO = "5etools-translator"
BACKUP_GITHUB_DEPLOYER_REPO = "5etools-translated-deployer"


def fork_repository(owner, repo, token, target_name):
    print(f"Forking backup in repo name {target_name}")
    url = f"https://api.github.com/repos/{owner}/{repo}/forks"
    data = {
        "name": target_name,
        "default_branch_only": True,
    }
    response = requests.post(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
        json=data,
    )

    if response.status_code == 202:
        print("Repository forked successfully")
        return response.json()["full_name"]
    else:
        raise Exception(f"Forking failed with status code {response.status_code}")


def use_repository_template(owner, repo, token, target_name):
    print(f"Duplicating template in repo name {target_name}")
    url = f"https://api.github.com/repos/{owner}/{repo}/generate"
    data = {
        "name": target_name,
        "include_all_branches": False,
    }
    response = requests.post(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
        json=data,
    )

    if response.status_code == 201:
        print("Template forked successfully")
        return response.json()["full_name"]
    else:
        raise Exception(f"Forking failed with status code {response.status_code}")


def create_repo_variable(owner, repo, variable, value, token):
    print(f"Creating variable {variable} in repo {repo}")
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/variables"
    data = {
        "name": variable,
        "value": value,
    }
    response = requests.post(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
        json=data,
    )

    if response.status_code == 201:
        print("Variable created successfully")
        return True
    else:
        raise Exception(f"Failed with status code {response.status_code}")


def create_repo_secret(owner, repo, name, value, token):
    print(f"Creating secret {name} in repo {repo}")
    public_key_response = get_repo_public_key(
        owner=DEPLOYER_GITHUB_USERNAME, repo=repo, token=DEPLOYER_GITHUB_TOKEN
    )
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/{name}"
    data = {
        "encrypted_value": encrypt(public_key_response["key"], value),
        "key_id": public_key_response["key_id"],
    }
    response = requests.put(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
        json=data,
    )

    if response.status_code == 201:
        print("Secret created successfully")
        return True
    else:
        raise Exception(f"Failed with status code {response.status_code}")


def set_pages_from_workflow(owner, repo, token):
    print(f"Setting Pages as deployed from workflow")
    url = f"https://api.github.com/repos/{owner}/{repo}/pages"
    data = {"build_type": "workflow"}
    response = requests.post(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
        json=data,
    )

    if response.status_code == 201:
        print("Page set successfully created successfully")
        return True
    else:
        raise Exception(f"Failed with status code {response.status_code}. Url: {url}")


def set_repo_settings(
    owner,
    repo,
    token,
    wiki: bool = False,
    projects: bool = False,
    issues: bool = False,
    is_template: bool = False,
):
    print(f"Setting the repo options")
    url = f"https://api.github.com/repos/{owner}/{repo}"
    data = {
        "has_issues": issues,
        "has_projects": projects,
        "has_wiki": wiki,
        "is_template": is_template,
    }
    response = requests.patch(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
        json=data,
    )

    if response.status_code == 200:
        print("Settings created successfully")
        return True
    else:
        raise Exception(f"Failed with status code {response.status_code}/ Url {url}")


def get_repo_public_key(owner, repo, token):
    print(f"Getting the repo public key")
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key"
    response = requests.get(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": GITHUB_API_VERSION,
        },
    )

    if response.status_code == 200:
        print("Key retrieved successfully")
        return response.json()
    else:
        raise Exception(f"Failed with status code {response.status_code}")


def encrypt(public_key: str, secret_value: str) -> str:
    """Encrypt a Unicode string using the public key."""
    public_key = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return b64encode(encrypted).decode("utf-8")


def create_translator_repo():
    # Create the translator repo
    forked_repo_full_name = fork_repository(
        owner=BACKUP_GITHUB_USERNAME,
        repo=BACKUP_GITHUB_TRANSLATOR_REPO,
        target_name=TRANSLATOR_GITHUB_REPO,
        token=TRANSLATOR_GITHUB_TOKEN,
    )
    set_repo_settings(
        owner=TRANSLATOR_GITHUB_USERNAME,
        repo=TRANSLATOR_GITHUB_REPO,
        token=TRANSLATOR_GITHUB_TOKEN,
        issues=True,
        wiki=False,
        project=False,
    )


def create_deployer_template_repo():
    # fork_repository(
    #     owner=BACKUP_GITHUB_USERNAME,
    #     repo=BACKUP_GITHUB_DEPLOYER_REPO,
    #     target_name="deployer_template",
    #     token=DEPLOYER_GITHUB_TOKEN,
    # )
    set_repo_settings(
        owner=DEPLOYER_GITHUB_USERNAME,
        repo="deployer_template",
        token=DEPLOYER_GITHUB_TOKEN,
        is_template=True,
    )


def create_deployer_repos():
    # Create all lang deployments repos
    deployments_lang = [
        "fr",
        "es",
        "de",
        "it",
        "ru",
        "zh",
        "pl",
        "sv",
        "nl",
    ]
    for lang in deployments_lang:
        print(f"Creating repo: {lang}")
        use_repository_template(
            owner=DEPLOYER_GITHUB_USERNAME,
            repo="deployer_template",
            target_name=lang,
            token=DEPLOYER_GITHUB_TOKEN,
        )

        time.sleep(10)

        create_repo_variable(
            owner=DEPLOYER_GITHUB_USERNAME,
            repo=lang,
            variable="DEPLOYMENT_LANGUAGE",
            value=lang,
            token=DEPLOYER_GITHUB_TOKEN,
        )
        create_repo_secret(
            owner=DEPLOYER_GITHUB_USERNAME,
            repo=lang,
            name="ACTIONS_TOKEN",
            value=DEPLOYER_GITHUB_TOKEN,
            token=DEPLOYER_GITHUB_TOKEN,
        )
        set_repo_settings(
            owner=DEPLOYER_GITHUB_USERNAME,
            repo=lang,
            token=DEPLOYER_GITHUB_TOKEN,
        )
        set_pages_from_workflow(
            owner=DEPLOYER_GITHUB_USERNAME, repo=lang, token=DEPLOYER_GITHUB_TOKEN
        )


if __name__ == "__main__":
    # create_translator_repo()
    # create_deployer_template_repo()
    create_deployer_repos()

    print("Finished recreating repos. Think to change the source in the backup repos.")
