import yaml
from hstest import StageTest, CheckResult, dynamic_test
from github import Github, GithubException
from AutoCoder.stage3.main import url
import os
import re


class GitTest(StageTest):
    g = Github(os.getenv("GITHUB_TOKEN")) if os.getenv("GITHUB_TOKEN") else Github()
    repo_name = url.split('/')[-1].replace('.git', '')
    username = url.split('/')[-2]
    full_repo_name = f"{username}/{repo_name}"
    repo = None

    def setup(self):
        if self.repo is None:
            self.repo = self.g.get_repo(self.full_repo_name)

    @classmethod
    def handle_github_exception(self, e):
        if e.status == 404:
            return CheckResult.wrong("The requested resource does not exist.")
        elif e.status == 403:
            return CheckResult.wrong("Access to the resource is forbidden or rate limit exceeded.")
        elif e.status == 401:
            return CheckResult.wrong("Authentication is required or has failed.")
        else:
            return CheckResult.wrong(f"An error occurred while accessing the GitHub repository: {e.data.get('message', 'No error message')}")

    @dynamic_test
    def check_main_file_exists(self):
        self.setup()
        try:
            files = self.repo.get_contents(".github/workflows")
            main_yaml_file = next((file for file in files if file.path in (".github/workflows/main.yml", ".github /workflows/main.yaml")), None)
            if main_yaml_file is None:
                return CheckResult.wrong(f"The main.yml or main.yaml file does not exist in the .github/workflows/ "
                                         f"directory.")
            return CheckResult.correct()
        except GithubException as e:
            return self.handle_github_exception(e)

    @dynamic_test
    def check_workflows_manifest(self):
        self.setup()
        try:
            main_yaml_file_path = ".github/workflows/main.yml"
            contents = self.repo.get_contents(main_yaml_file_path)
            workflow_file = contents.decoded_content.decode()
            new_workflow = yaml.load(workflow_file, Loader=yaml.BaseLoader)

            if "on" not in new_workflow or "issues" not in new_workflow["on"]:
                return CheckResult.wrong("The workflow does not run on issues.")

            issues_types = new_workflow["on"]["issues"]["types"]
            if "opened" not in issues_types or "reopened" not in issues_types:
                return CheckResult.wrong("The workflow does not run on opened and reopened issues.")

            if "jobs" not in new_workflow:
                return CheckResult.wrong("The workflow does not have a job.")

            job_name, job = next(iter(new_workflow["jobs"].items()), (None, None))
            if not job or job.get("runs-on") != "ubuntu-latest":
                return CheckResult.wrong("The job does not run on 'ubuntu-latest' runner or is missing.")

            # check for checkout repository action
            if not any(re.fullmatch(r"actions/checkout@v\d+(\.\d+)*", step.get("uses", "")) for step in job["steps"]):
                return CheckResult.wrong("The job does not have the 'actions/checkout' step.")

            if "steps" not in job:
                return CheckResult.wrong("The job does not have any steps defined.")

            required_envs = [
                "${{ github.event.issue.number }}",
                "${{ github.event.issue.title }}",
                "${{ github.event.issue.body }}",
                "${{ join(github.event.issue.labels.*.name, ', ') }}",
                "${{ join(github.event.issue.assignees.*.login, ', ') }}"
            ]

            env_vars = []
            for job in new_workflow.get("jobs", {}).values():
                if "steps" in job:
                    for step in job.get("steps", []):
                        if "env" in step:
                            for key, value in step["env"].items():
                                if value in required_envs:
                                    env_vars.append(value)

            missing_env_vars = [env_var for env_var in required_envs if env_var not in env_vars]

            if missing_env_vars:
                return CheckResult.wrong(f"The following environment variables are missing in the 'env' key of a step: {', '.join(missing_env_vars)}")
            return CheckResult.correct()
        except GithubException as e:
            return self.handle_github_exception(e)

    @dynamic_test
    def check_issues_exist(self):
        self.setup()
        try:
            issues = list(self.repo.get_issues(state="open"))
            if not issues:
                return CheckResult.wrong("No open issues found in the repository.")
            return CheckResult.correct()
        except GithubException as e:
            return self.handle_github_exception(e)

    @dynamic_test
    def check_workflow_run_on_issues(self):
        self.setup()
        try:
            latest_workflow_run = next(iter(self.repo.get_workflow_runs().get_page(0)), None)
            if latest_workflow_run is None or latest_workflow_run.event != "issues":
                return CheckResult.wrong(f"The latest workflow run was not triggered by an issue event.")
            if latest_workflow_run.conclusion != "success":
                return CheckResult.wrong(f"The latest workflow run did not succeed.")
            return CheckResult.correct()
        except GithubException as e:
            return self.handle_github_exception(e)
