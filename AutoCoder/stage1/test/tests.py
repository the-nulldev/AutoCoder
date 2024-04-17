from hstest import StageTest, CheckResult, dynamic_test
from github import Github
from github import GithubException
import os

from AutoCoder.stage1.main import url


class GitTest(StageTest):
    g = Github(os.getenv("GITHUB_TOKEN")) if os.getenv("GITHUB_TOKEN") else Github()

    @dynamic_test
    def check_url_set(self):
        if url == "":
            return CheckResult.wrong("The URL in main.py is not set.")
        return CheckResult.correct()

    @dynamic_test()
    def check_repo(self):
        repo_name = url.split('/')[-1].replace('.git', '')  # Remove .git if present
        username = url.split('/')[-2]
        full_repo_name = f"{username}/{repo_name}"

        try:
            # Call get_repo once and store the result
            repo = self.g.get_repo(full_repo_name)

            # Check if the repository is public
            if repo.private:
                return CheckResult.wrong("The repository is private. Make sure it's public.")

            # List of expected files and directories
            expected_files = {"README.md", ".github/workflows/main.yml", "scripts/script.sh"}

            # Use a set to track all top-level paths in the repository
            repo_contents = set()

            # Recursively check all files and directories in the repository
            def check_directory_contents(contents_url, path=""):
                contents = repo.get_contents(path)
                for content in contents:
                    if content.type == "dir":
                        check_directory_contents(contents_url, content.path)
                    else:
                        repo_contents.add(content.path)

            check_directory_contents(repo.get_contents(""))

            # Check for missing expected files
            missing_files = expected_files - repo_contents
            if missing_files:
                missing_files_str = ', '.join(missing_files)
                return CheckResult.wrong(f"The repository is missing the following expected file(s): {missing_files_str}")

            # Check for extra unexpected files
            extra_files = repo_contents - expected_files
            if extra_files:
                extra_files_str = ', '.join(extra_files)
                return CheckResult.wrong(f"The repository contains unexpected file(s): {extra_files_str}")

            # check if the README.md file contains any content, the repository name and content is more than 50 words
            readme_content = repo.get_contents("README.md").decoded_content.decode()
            if readme_content == "":
                return CheckResult.wrong("The README.md file is empty.")
            if repo_name not in readme_content:
                return CheckResult.wrong("The README.md file does not contain the repository name.")
            if len(readme_content.split()) < 50:
                return CheckResult.wrong("The project description is too short.")
            return CheckResult.correct()

        except GithubException as e:
            if e.status == 404:
                return CheckResult.wrong("The repository does not exist or is private.")
            else:
                return CheckResult.wrong(f"An error occurred while accessing the repository: {e.data.get('message', 'No error message')}")
        except Exception as e:
            return CheckResult.wrong(f"An unexpected error occurred: {e}")


if __name__ == '__main__':
    GitTest().run_tests()
