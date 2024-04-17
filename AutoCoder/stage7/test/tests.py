import yaml
from hstest import StageTest, CheckResult, dynamic_test
from github import Github, GithubException
import os
import re
from AutoCoder.stage7.main import url


class GitTest(StageTest):
    g = Github(os.getenv("GITHUB_TOKEN")) if os.getenv("GITHUB_TOKEN") else Github()
    repo_name = url.split('/')[-1].replace('.git', '')
    username = url.split('/')[-2]
    full_repo_name = f"{username}/{repo_name}"
    repo = g.get_repo(full_repo_name)

    @classmethod
    def handle_github_exception(self, e):
        if e.status == 404:
            return CheckResult.wrong("You attempted to access a non-existent resource. Check and try again.")
        elif e.status == 403:
            return CheckResult.wrong("Access to the resource is forbidden or rate limit exceeded.")
        elif e.status == 401:
            return CheckResult.wrong("Authentication is required or has failed.")
        else:
            return CheckResult.wrong(f"An error occurred while accessing the GitHub repository: {e.data.get('message', 'No error message')}")

    @dynamic_test
    def check_action_file_exists(self):
        try:
            contents = self.repo.get_contents("action.yml")
            if not contents:
                return CheckResult.wrong("The file 'action.yml' does not exist.")
            return CheckResult.correct()
        except GithubException as e:
            return self.handle_github_exception(e)
        except Exception as e:
            return CheckResult.wrong(f"Something went wrong. Encountered: {e}")

    @dynamic_test
    def check_action_file_contents(self):
        try:
            contents = self.repo.get_contents("action.yml")
            action_file = contents.decoded_content.decode()
            action_metadata = yaml.load(action_file, Loader=yaml.BaseLoader)

            # Checking the name of the action
            if action_metadata.get("name") != "AutoCoder":
                return CheckResult.wrong("The name of the action in 'action.yml' should be 'AutoCoder'.")

            # Checking required inputs
            required_inputs = ["GITHUB_TOKEN", "REPOSITORY", "ISSUE_NUMBER", "OPENAI_API_KEY", "SCRIPT_PATH", "LABEL"]
            for input_name in required_inputs:
                if input_name not in action_metadata.get("inputs", {}):
                    return CheckResult.wrong(f"The input '{input_name}' is missing in 'action.yml'.")

            # Checking if the action uses 'composite' runs
            if action_metadata.get("runs", {}).get("using") != "composite":
                return CheckResult.wrong("The 'action.yml' should specify that it's using 'composite' for 'runs'.")

            steps = action_metadata.get("runs", {}).get("steps", [])
            if not steps:
                return CheckResult.wrong("The 'runs' section of 'action.yml' does not have any steps.")

            expected_steps = {
                "make_the_script_executable": "chmod +x",
                "checkout__the_repository": "actions/checkout@",
                "create_pull_request": "peter-evans/create-pull-request@",
                "configure_credentials_or_commit_files": "git config --local user.email \"actions@github.com\"\n"
                                                         "git config --local user.name \"autocoder-bot\"\n"
                                                         "git add .\n"
                                                         "git commit -m",
            }

            for step_name, expected_value in expected_steps.items():
                # Use startswith for all steps
                if not any(step.get("run", "").startswith(expected_value) or step.get("uses", "").startswith(expected_value) for step in steps):
                    return CheckResult.wrong(f"The job does not have a step to {step_name.replace('_', ' ')}.")

            return CheckResult.correct()
        except Exception as e:
            return CheckResult.wrong(f"Something went wrong while checking 'action.yml'. Encountered: {e}")

    @dynamic_test
    def check_main_file_exists(self):
        try:
            files = self.repo.get_contents(".github/workflows")
            main_yaml_file_exists = any(
                file.path == ".github/workflows/main.yml" or file.path == ".github/workflows/main.yaml" for file in files)
            if not main_yaml_file_exists:
                return CheckResult.wrong(f"The main.yml file does not exist in the .github/workflows/ directory.")
            return CheckResult.correct()
        except Exception as e:
            return CheckResult.wrong(f"Something went wrong. Encountered: {e}")

    @dynamic_test
    def check_workflow_manifest(self):
        try:
            contents = self.repo.get_contents(".github/workflows/main.yml")
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

            steps = job.get("steps", [])

            expected_steps = {
                "checkout__the_repository": "actions/checkout@",
                "interact_with_ChatGPT": f"{self.full_repo_name}@",
            }

            for step_name, expected_value in expected_steps.items():
                # Use startswith for all steps
                if not any(step.get("uses", "").startswith(expected_value) for step in steps):
                    return CheckResult.wrong(f"The job does not have a step to {step_name.replace('_', ' ')}.")

            return CheckResult.correct()
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
            return CheckResult.correct()

        except Exception as e:
            return CheckResult.wrong(f"Something went wrong. Encountered: {e}")

    @dynamic_test
    def check_pull_request_details(self):
        try:
            # Get a list of recent pull requests
            pull_requests = list(self.repo.get_pulls(state='open', sort='created', direction='desc'))

            if not pull_requests:
                return CheckResult.wrong("No open pull requests found in the repository.")

            # Assume the first PR is the one we want to check
            pr = pull_requests[0]

            # Check if the pull request was created by GitHub Actions
            if pr.user.login != 'github-actions[bot]':
                return CheckResult.wrong("The pull request was not created by GitHub Actions.")

            # Check if the pull request has the 'autocoder-bot' label
            if 'autocoder-bot' not in [label.name for label in pr.labels]:
                return CheckResult.wrong("The pull request does not have the 'autocoder-bot' label.")

            # Check if the pull request has no conflicts with the base branch
            if pr.mergeable_state != 'clean':
                return CheckResult.wrong("The pull request has conflicts with the base branch. Rerun the workflow.")

            # Verify commit author details
            commits = list(pr.get_commits())
            for commit in commits:
                author_name = commit.commit.author.name
                author_email = commit.commit.author.email
                if author_name != "autocoder-bot" or author_email != "actions@github.com":
                    return CheckResult.wrong(
                        "The commit was not made by 'autocoder-bot' with the email 'actions@github.com'. "
                        f"Found name: '{author_name}', email: '{author_email}'."
                    )

            # Extract the issue number from the pull request title
            issue_number = re.search(r"#(\d+)", pr.title).group(1)

            # Check if the pull request branch follows the naming convention 'autocoder-branch-issueNumber'
            expected_branch_name = f"autocoder-branch-{issue_number}"
            if pr.head.ref != expected_branch_name:
                return CheckResult.wrong(f"The pull request branch name does not follow the convention "
                                         f"'autocoder-branch-issueNumber'. Expected '{expected_branch_name}', "
                                         f"found '{pr.head.ref}'.")
            return CheckResult.correct()
        except Exception as e:
            return CheckResult.wrong(f"Something went wrong. Encountered: {e}")


if __name__ == '__main__':
    GitTest().run_tests()
