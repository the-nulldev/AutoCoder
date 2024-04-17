import yaml
from hstest import StageTest, CheckResult, dynamic_test
from github import Github
from github import GithubException
from AutoCoder.stage2.main import url
import os
import re

echo_command = re.compile(r"echo\s+[\"']Hello,\s+world![\"']", re.IGNORECASE)


class GitTest(StageTest):
    g = Github(os.getenv("GITHUB_TOKEN")) if os.getenv("GITHUB_TOKEN") else Github()

    repo_name = url.split('/')[-1]
    username = url.split('/')[-2]
    full_repo_name = f"{username}/{repo_name}"
    repo = g.get_repo(full_repo_name)

    @dynamic_test
    def check_url_set(self):
        if url == "":
            return CheckResult.wrong("The URL in main.py is not set.")
        return CheckResult.correct()

    @dynamic_test
    def check_main_file_exists(self):
        try:
            contents = self.repo.get_contents(".github/workflows")
            main_yaml_file_exists = any(
                content.path == ".github/workflows/main.yml" or content.path == ".github/workflows/main.yaml" for
                content in contents)
            if not main_yaml_file_exists:
                return CheckResult.wrong(f"The main.yml file does not exist in the .github/workflows/ directory.")
            return CheckResult.correct()
        except GithubException as e:
            if e.status == 404:
                return CheckResult.wrong("The .github/workflows directory does not exist or cannot be accessed.")
            else:
                return CheckResult.wrong(
                    f"An error occurred while accessing the GitHub repository: {e.data.get('message', 'No error message')}")
        except Exception as e:
            return CheckResult.wrong(f"Something went wrong. Encountered: {e}")

    @dynamic_test
    def check_workflow_manifest(self):
        try:
            contents = self.repo.get_contents(".github/workflows/main.yml")
            workflow_file = contents.decoded_content.decode()
            new_workflow = yaml.load(workflow_file, Loader=yaml.BaseLoader)

            if not new_workflow:
                return CheckResult.wrong("The workflow file is empty.")

            if "on" not in new_workflow or "push" not in new_workflow["on"]:
                return CheckResult.wrong("The workflow does not run on push.")
            #  check the main branch
            if "branches" in new_workflow["on"]:
                if "main" not in new_workflow["on"]["branches"]:
                    return CheckResult.wrong("The workflow does not run on the main branch.")

            jobs = new_workflow.get("jobs")
            if not jobs:
                return CheckResult.wrong("The workflow does not have a job.")

            job_name, job = next(iter(jobs.items()), (None, None))

            if not job or job.get("runs-on") != "ubuntu-latest":
                return CheckResult.wrong("The job does not run on 'ubuntu-latest' runner or is missing.")

            steps = job.get("steps", [])

            expected_steps = {
                "checkout_repository": "actions/checkout@",
                "print_hello_world_using_the_echo_command": "echo"
            }

            for step_name, expected_value in expected_steps.items():
                # Use startswith for all steps
                if not any(step.get("uses", "").startswith(expected_value) for step in steps):
                    return CheckResult.wrong(f"The job does not have a step to {step_name.replace('_', ' ')}.")
            return CheckResult.correct()
        except GithubException as e:
            if e.status == 404:
                return CheckResult.wrong("The .github/workflows directory does not exist or cannot be accessed.")
            elif e.status == 403:
                return CheckResult.wrong("Rate limit exceeded. Please try again later or set the GITHUB_TOKEN environment variable.")
            else:
                return CheckResult.wrong(
                    f"An error occurred while accessing the GitHub repository: {e.data.get('message', 'No error message')}")
        except Exception as e:
            return CheckResult.wrong(f"Something went wrong. Encountered: {e}")

    @dynamic_test
    def check_workflow_run_on_push(self):
        try:
            latest_workflow_run = list(self.repo.get_workflow_runs().get_page(0))[0]
            if latest_workflow_run.event != "push":
                return CheckResult.wrong(f"The latest workflow run was not triggered by a push event.")
            if latest_workflow_run.conclusion != "success":
                return CheckResult.wrong(f"The latest workflow run did not succeed.")
            return CheckResult.correct()

        except GithubException as e:
            if e.status == 404:
                return CheckResult.wrong("No workflow runs found or the workflows cannot be accessed.")
            else:
                return CheckResult.wrong(
                    f"An error occurred while accessing the GitHub repository: {e.data.get('message', 'No error message')}")
        except Exception as e:
            return CheckResult.wrong(f"Something went wrong. Encountered: {e}")


if __name__ == '__main__':
    GitTest().run_tests()
