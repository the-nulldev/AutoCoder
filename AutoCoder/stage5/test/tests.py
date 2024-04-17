import yaml
from hstest import StageTest, CheckResult, dynamic_test
from github import Github, GithubException
from AutoCoder.stage5.main import url
import os
import re


class GitTest(StageTest):
    g = Github(os.getenv("GITHUB_TOKEN")) if os.getenv("GITHUB_TOKEN") else Github()

    repo_name = url.split('/')[-1].replace('.git', '')
    username = url.split('/')[-2]
    full_repo_name = f"{username}/{repo_name}"
    repo = g.get_repo(full_repo_name)

    @classmethod
    def handle_github_exception(cls, e):
        if e.status == 404:
            return CheckResult.wrong("The requested resource does not exist.")
        elif e.status == 403:
            return CheckResult.wrong("Access to the resource is forbidden or rate limit exceeded.")
        elif e.status == 401:
            return CheckResult.wrong("Authentication is required or has failed.")
        else:
            return CheckResult.wrong(f"An error occurred while accessing the GitHub repository: {e.data.get('message', 'No error message')}")

    @dynamic_test
    def check_script_file_contents(self):
        try:
            contents = self.repo.get_contents("scripts/script.sh")
            if not contents:
                return CheckResult.wrong("The file 'scripts/script.sh' does not exist.")
            # check if the script file is empty
            if not contents.decoded_content:
                return CheckResult.wrong("The file 'scripts/script.sh' is empty.")
            return CheckResult.correct()
        except GithubException as e:
            return self.handle_github_exception(e)
        except Exception as e:
            return CheckResult.wrong(f"Something went wrong. Encountered: {e}")

    @dynamic_test
    def check_main_file_exists(self):
        try:
            files = self.repo.get_contents(".github/workflows")
            main_yaml_file_exists = any(
                file.path == ".github/workflows/main.yml" or file.path == ".github/workflows/main.yaml" for
                file in files)
            if not main_yaml_file_exists:
                return CheckResult.wrong(f"The main.yml file does not exist in the .github/workflows/ directory.")
            return CheckResult.correct()
        except GithubException as e:
            return self.handle_github_exception(e)
        except Exception as e:
            return CheckResult.wrong(f"Something went wrong. Encountered: {e}")

    @dynamic_test
    def check_workflow_manifest(self):
        try:
            contents = self.repo.get_contents(".github/workflows/main.yml") or self.repo.get_contents(
                ".github/workflows/main.yaml")

            workflow_file = contents.decoded_content.decode()
            new_workflow = yaml.load(workflow_file, Loader=yaml.BaseLoader)

            if new_workflow.get("on", {}).get("issues", {}).get("types") != ["opened", "reopened", "labeled"]:
                return CheckResult.wrong("The workflow does not run on opened, reopened, and labeled issues.")

            jobs = new_workflow.get("jobs")
            if not jobs:
                return CheckResult.wrong("The workflow does not have a job.")

            job_name, job = next(iter(jobs.items()), (None, None))

            if not job or job.get("runs-on") != "ubuntu-latest":
                return CheckResult.wrong("The job does not run on 'ubuntu-latest' runner or is missing.")

            # check for the if condition checking the autocoder-bot label
            if not any(job.get("if") == "contains(github.event.issue.labels.*.name, 'autocoder-bot')" for step in job.get("steps", [])):
                return CheckResult.wrong("The job does not have a check for the 'autocoder-bot' label.")

            steps = job.get("steps", [])

            expected_steps = {
                "make_script_file_executable": "chmod",
                "checkout_repository": r"actions/checkout@v",
                "upload_artifact": "actions/upload-artifact@v",
                "download_artifact": "actions/download-artifact@v",
                "list_files": "ls -R ./autocoder-artifact",
                "run_the_script": "./scripts/script.sh $"
            }
            for step_name, expected_value in expected_steps.items():
                # Use startswith for all steps
                if not any(step.get("run", "").startswith(expected_value) or step.get("uses", "").startswith(expected_value) for step in steps):
                    return CheckResult.wrong(f"The job does not have a step to {step_name.replace('_', ' ')}.")
            return CheckResult.correct()
        except GithubException as e:
            return self.handle_github_exception(e)
        except Exception as e:
            return CheckResult.wrong(f"Something went wrong. Encountered: {e}")

    @dynamic_test
    def check_issues_exist(self):
        try:
            issues = list(self.repo.get_issues(state="open"))
            if not issues:
                return CheckResult.wrong("No open issues found in the repository.")
            return CheckResult.correct()
        except GithubException as e:
            return self.handle_github_exception(e)
        except Exception as e:
            return CheckResult.wrong(f"Something went wrong. Encountered: {e}")

    @dynamic_test
    def check_issue_properties(self):
        try:
            issues = list(self.repo.get_issues(state="open", labels=["autocoder-bot"]))
            for issue in issues:
                if not issue.body:
                    return CheckResult.wrong(f"The issue #{issue.number} does not have any content.")
            return CheckResult.correct()
        except GithubException as e:
            return self.handle_github_exception(e)
        except Exception as e:
            return CheckResult.wrong(f"Something went wrong. Encountered: {e}")

    @dynamic_test
    def check_workflow_run_on_issues(self):
        try:
            latest_workflow_run = list(self.repo.get_workflow_runs().get_page(0))[0]
            if latest_workflow_run.event != "issues":
                return CheckResult.wrong(f"The latest workflow run was not triggered by an issue event.")
            if latest_workflow_run.conclusion != "success":
                return CheckResult.wrong(f"The latest workflow run did not succeed.")
            artifacts = list(latest_workflow_run.get_artifacts())
            if not artifacts:
                return CheckResult.wrong("No artifacts found in the latest workflow run.")
            # check if the artifact is named "autocoder-artifact"
            if artifacts[0].name != "autocoder-artifact":
                return CheckResult.wrong("The uploaded artifact is not named 'autocoder-artifact'.")
            return CheckResult.correct()
        except GithubException as e:
            return self.handle_github_exception(e)
        except Exception as e:
            return CheckResult.wrong(f"Something went wrong. Encountered: {e}")


if __name__ == '__main__':
    GitTest().run_tests()
