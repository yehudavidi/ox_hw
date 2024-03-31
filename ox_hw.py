import argparse
import logging
import sys
import requests
import pydot

from graphviz import Source

GITHUB_API_URL = 'https://api.github.com'
REPO_OWNER = 'yehudavidi'
REPO_OWNER = 'CTFd'
REPO_NAME = 'CTFd'


class GitGit:
    def __init__(self, token: str, dot_file: str='graph',
                 log_file: str=None, debug: bool=False) -> None:
        self.token = token
        self.dot_file = dot_file
        self.log_file = log_file
        self.debug = debug
        self.setup_logger()
        if log_file is None:
            self.logger.info('Logging to stdout')
        else:
            self.logger.info('Logging to file: %s', log_file)

        self.logger.debug('GitHub Token: %s', token)

    def get_latest_releases(self):
        headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        url = f'{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/releases'
        response = requests.get(url, headers=headers)
        releases = response.json()
        return releases[:3]

    def get_repo_info(self):
        headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        url = f'{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}'
        response = requests.get(url, headers=headers)
        repo_info = response.json()
        return repo_info

    def get_contributors(self):
        headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        url = f'{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/contributors?per_page=300&page='
        i = 1
        contributors = []
        new_contributors = None
        while new_contributors != []:
            response = requests.get(f'{url}{i}', headers=headers)
            new_contributors = response.json()
            contributors.extend(new_contributors)
            i += 1
        return contributors

    def get_pull_requests(self):
        headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.text+json'
        }
        url = f'{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/pulls'
        self.num_of_pull_request = 0
        pull_requests = None
        i = 1
        contributors = {}
        while pull_requests != []:
            response = requests.get(
                url=f'{url}?page={i}',
                headers=headers
            )
            pull_requests = response.json()
            self.num_of_pull_request += len(pull_requests)
            for pull_request in pull_requests:
                user_name = pull_request['user']['login']
                if user_name not in contributors:
                    contributors[user_name] = 0
                contributors[user_name] += 1
            i += 1
        self.contributors = sorted(
            contributors,
            key=contributors.get,
            reverse=True
        )

    def find_pull_request(self, pull_url: str = None):
        headers = {
            'Authorization': f'token {self.token}',
            'Accept': 'application/vnd.github.text+json'
        }
        if pull_url is None:
            url = f'{GITHUB_API_URL}/repos/{REPO_OWNER}/{REPO_NAME}/pulls?state=closed'
            merged_pulls = []
            i = 1
            while merged_pulls == []:
                response = requests.get(
                    url=f'{url}?page={i}',
                    headers=headers
                )
                pulls = response.json()
                merged_pulls = [pull for pull in pulls if pull['merged_at'] is not None]
                i += 1
            if merged_pulls == []:
                raise Exception('Merged pull was not found')
            merged_pull = merged_pulls[0]
        else:
            response = requests.get(
                url=pull_url,
                headers=headers
            )
            merged_pull = response.json()
        commit_url = merged_pull['commits_url']
        response = requests.get(
            url=commit_url,
            headers=headers
        )
        self.commits = [
            {
                'sha': commit['sha'],
                'author': commit['commit']['author'],
                'message': commit['commit']['message'],
                'parents': commit['parents'],
                'type': 'commit'
            }
            for commit in response.json()
        ]
        keys_to_update = ('id', 'number', 'title',
                        'body', 'created_at', 'merged_at',
                        'merge_commit_sha')
        self.pull_info = {
            key1: {
                key2: merged_pull[key1][key2]
                for key2 in ('label', 'sha')
            }
            for key1 in ('head', 'base')
        }
        for key in keys_to_update:
            self.pull_info[key] = merged_pull[key]

    def create_commit_graph(self):
        self.graph = pydot.Dot(graph_type='digraph')
        source_branch = self.pull_info['head']['label']
        for commit in self.commits:
            commit_id = commit['sha']
            commit['branch'] = source_branch
            label = (
                f'{commit_id}\n'
                f"message: {commit['message'][:10]}\n"
                f"branch: {commit['branch']}\n"
            )
            node = pydot.Node(
                name=commit_id,
                label=label
            )
            self.graph.add_node(node)

            if 'parents' in commit and len(commit['parents']) > 0:
                parent_id = commit['parents'][0]['sha']
                edge = pydot.Edge(
                    parent_id,
                    commit_id,
                    style='dashed'
                )
                self.graph.add_edge(edge)
        label = (
            'PULL\n'
            f'branch: {source_branch}\n'
            f"{self.pull_info['base']['sha']}"
        )
        node = pydot.Node(
            self.pull_info['base']['sha'],
            label=label,
            shape='box'
        )
        self.graph.add_node(node)
        edge = pydot.Edge(
            self.pull_info['head']['sha'],
            self.pull_info['base']['sha']
        )
        self.graph.add_edge(edge)
        label = (
            'MERGE\n'
            f"branch: {self.pull_info['base']['label']}\n"
            f"{self.pull_info['merge_commit_sha']}"
        )
        node = pydot.Node(
            self.pull_info['merge_commit_sha'],
            label=label,
            shape='diamond'
        )
        self.graph.add_node(node)
        edge = pydot.Edge(
            self.pull_info['base']['sha'],
            self.pull_info['merge_commit_sha'],
            penwidth=5
        )
        self.graph.add_edge(edge)

    def output_graph(self):
        self.graph.write(f'{self.dot_file}.dot')
        dot_string = self.graph.to_string()
        graph = Source(dot_string)
        graph.render(
            filename=self.dot_file,
            format='png',
            view=False
        )

    def setup_logger(self):
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.DEBUG if self.debug else logging.INFO)

        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

        if self.log_file is None:
            handler = logging.StreamHandler(sys.stdout)
        else:
            handler = logging.FileHandler(self.log_file)
        handler.setLevel(logging.DEBUG if self.debug else logging.INFO)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def log(self, *args):
        self.logger.info(*args)

def main():
    parser = argparse.ArgumentParser(description='CTFd Repo Information')

    parser.add_argument('--token', help='GitHub token for authentication')
    parser.add_argument('--log-file', default=None, help='Log file to write logs into')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--dot-file', default='graph', help='Output file for graph (default: graph.dot)')

    args = parser.parse_args()

    gitgit = GitGit(
        token=args.token,
        dot_file=args.dot_file,
        log_file=args.log_file,
        debug = args.debug
    )

    gitgit.log('Fetching latest 3 releases...')
    releases = gitgit.get_latest_releases()
    
    gitgit.log('Latest 3 releases: %s', [release['name'] for release in releases])

    gitgit.log('Fetching repo information...')
    repo_info = gitgit.get_repo_info()
    gitgit.log('Forks: %s', repo_info['forks'])
    gitgit.log('Stars: %s', repo_info['stargazers_count'])

    gitgit.log('Fetching contributors...')
    contributors = gitgit.get_contributors()
    gitgit.log('Number of contributors: %s', len(contributors))

    gitgit.log('Fetching pull requests...')
    gitgit.get_pull_requests()
    gitgit.log('Number of pull requests: %s', gitgit.num_of_pull_request)
    gitgit.log('and its contributors:\n%s\n', '\n'.join(gitgit.contributors))

    gitgit.find_pull_request(
        pull_url="https://api.github.com/repos/CTFd/CTFd/pulls/2420"
    )
    gitgit.create_commit_graph()

    gitgit.log('Outputting graph to dot file: %s.dot', args.dot_file)
    gitgit.output_graph()

    gitgit.log('Program execution completed successfully.')


if __name__ == '__main__':
    main()