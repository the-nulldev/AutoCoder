import yaml
from hstest import StageTest, CheckResult, dynamic_test
from github import Github, GithubException
from AutoCoder.stage4.main import url
import os


class GitTest(StageTest):
    g = Github(os.getenv("GITHUB_TOKEN")) if os.getenv("GITHUB_TOKEN") else Github()

    repo_name = url.split('/')[-1]
    username = url.split('/')[-2]
    full_repo_name = f"{username}/{repo_name}"
    repo = g.get_repo(full_repo_name)

    def setup(self):
        if self.repo is None:
            self.repo = self.g.get_repo(self.full_repo_name)

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
    def check_issues_exist(self):
        try:
            issues = list(self.repo.get_issues(state="open"))
            if not issues:
                return CheckResult.wrong("No open issues found in the repository.")
            return CheckResult.correct()
        except GithubException as e:
            return self.handle_github_exception(e)

    @dynamic_test
    def check_issue_properties(self):
        try:
            issues = [issue for issue in self.repo.get_issues(state="open", labels=["autocoder-bot"]) if issue.pull_request is None]
            for issue in issues:
                if not issue.labels:
                    return CheckResult.wrong(f"The issue #{issue.number} does not have any labels.")
                if not issue.body:
                    return CheckResult.wrong(f"The issue #{issue.number} does not have any content.")
                if not issue.labels[0].name == "autocoder-bot":
                    return CheckResult.wrong(f"The issue #{issue.number} does not have the label 'autocoder-bot'.")
                if len(issue.body.split()) < 50:
                    return CheckResult.wrong(f"The issue #{issue.number} is too short. Please provide more details.")
            return CheckResult.correct()
        except GithubException as e:
            return self.handle_github_exception(e)
        except Exception as e:
            return CheckResult.wrong(f"An error occurred while checking the issue properties. Encountered: {e}")


if __name__ == '__main__':
    GitTest().run_tests()