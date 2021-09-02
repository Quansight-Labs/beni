from copy import deepcopy
from pathlib import Path

import yaml
from _pytest.capture import CaptureFixture

from beni import main

proj_dir = Path(__file__).parent.parent
pyproj_path = proj_dir / "pyproject.toml"
environment = yaml.safe_load((proj_dir / "environment.yml").read_text())

dev_deps = ["pre-commit", "ipython"]
test_deps = ["pytest"]


def sort_environments(*envs):
    for d in envs:
        d["dependencies"] = [d["dependencies"][0], *sorted(d["dependencies"][1:])]


def test_run_basic(capsys: CaptureFixture):
    expected = deepcopy(environment)
    main([str(pyproj_path)])
    actual = yaml.safe_load(capsys.readouterr().out)
    sort_environments(expected, actual)
    assert expected == actual


def test_run_prod_deps(capsys: CaptureFixture):
    expected = deepcopy(environment)
    for dep in dev_deps + test_deps:
        assert dep in expected["dependencies"]
        expected["dependencies"].remove(dep)
    main([str(pyproj_path), "--deps=production"])
    actual = yaml.safe_load(capsys.readouterr().out)
    sort_environments(expected, actual)
    assert expected == actual


def test_run_dev_extra(capsys: CaptureFixture):
    expected = deepcopy(environment)
    for dep in test_deps:
        expected["dependencies"].remove(dep)
    main([str(pyproj_path), "--extras=dev"])
    actual = yaml.safe_load(capsys.readouterr().out)
    sort_environments(expected, actual)
    assert expected == actual
