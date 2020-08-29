from copy import deepcopy
from pathlib import Path

import yaml
from _pytest.capture import CaptureFixture

from beni import main


proj_dir = Path(__file__).parent.parent
pyproj_path = proj_dir / "pyproject.toml"
environment = yaml.load((proj_dir / "environment.yml").read_text())


def sort_environments(*envs):
    for d in envs:
        d['dependencies'] = [d['dependencies'][0], *sorted(d['dependencies'][1:])]


def test_run_basic(capsys: CaptureFixture):
    expected = deepcopy(environment)
    main([str(pyproj_path)])
    actual = yaml.load(capsys.readouterr().out)
    sort_environments(expected, actual)
    assert expected == actual
