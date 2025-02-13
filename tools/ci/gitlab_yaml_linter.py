#!/usr/bin/env python

# SPDX-FileCopyrightText: 2023 Espressif Systems (Shanghai) CO LTD
# SPDX-License-Identifier: Apache-2.0

"""
Check gitlab ci yaml files
"""

import argparse
import os
import typing as t
from functools import cached_property

from idf_ci_utils import IDF_PATH, GitlabYmlConfig, get_submodule_dirs


class YmlLinter:
    def __init__(self, yml_config: GitlabYmlConfig) -> None:
        self.yml_config = yml_config

        self._errors: t.List[str] = []

    @cached_property
    def lint_functions(self) -> t.List[str]:
        funcs = []
        for func in dir(self):
            if func.startswith('_lint_'):
                funcs.append(func)

        return funcs

    def lint(self) -> None:
        exit_code = 0

        for func in self.lint_functions:
            getattr(self, func)()

            if self._errors:
                print(f'Errors found while running {func}:')
                exit_code = 1
                print('\t- ' + '\n\t- '.join(self._errors))
                self._errors = []  # reset

        exit(exit_code)

    # name it like _1_ to make it run first
    def _lint_1_yml_parser(self) -> None:
        for k, v in self.yml_config.config.items():
            if (
                k not in self.yml_config.global_keys
                and k not in self.yml_config.anchors
                and k not in self.yml_config.jobs
            ):
                raise SystemExit(f'Parser incorrect. Key {k} not in global keys, rules or jobs')

    def _lint_default_values_artifacts(self) -> None:
        defaults_artifacts = self.yml_config.default.get('artifacts', {})

        for job_name, d in self.yml_config.jobs.items():
            for k, v in d.get('artifacts', {}).items():
                if k not in defaults_artifacts:
                    continue

                if v == defaults_artifacts[k]:
                    self._errors.append(f'job {job_name} key {k} has same value as default value {v}')

    def _lint_submodule_patterns(self) -> None:
        submodule_paths = sorted(['.gitmodules'] + get_submodule_dirs())
        submodule_paths_in_patterns = sorted(self.yml_config.config.get('.patterns-submodule', []))

        if submodule_paths != submodule_paths_in_patterns:
            unused_patterns = set(submodule_paths_in_patterns) - set(submodule_paths)
            if unused_patterns:
                for item in unused_patterns:
                    self._errors.append(f'non-exist pattern {item}. Please remove {item} from .patterns-submodule')
            undefined_patterns = set(submodule_paths) - set(submodule_paths_in_patterns)
            if undefined_patterns:
                for item in undefined_patterns:
                    self._errors.append(f'undefined pattern {item}. Please add {item} to .patterns-submodule')

    def _lint_gitlab_yml_rules(self) -> None:
        unused_rules = self.yml_config.rules - self.yml_config.used_rules
        for item in unused_rules:
            self._errors.append(f'Unused rule: {item}, please remove it')
        undefined_rules = self.yml_config.used_rules - self.yml_config.rules
        for item in undefined_rules:
            self._errors.append(f'Undefined rule: {item}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--root-yml-filepath', help='root yml file path', default=os.path.join(IDF_PATH, '.gitlab-ci.yml')
    )
    args = parser.parse_args()

    config = GitlabYmlConfig(args.root_yml_filepath)
    linter = YmlLinter(config)
    linter.lint()
