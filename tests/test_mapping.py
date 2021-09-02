from packaging.requirements import Requirement

from beni import generate_environment


def test_not_on_pip():
    env = generate_environment("wants-rdkit", "=3.7", [Requirement("rdkit")])
    assert env["dependencies"] == [dict(pip=["flit"]), "python=3.7", "pip", "rdkit"]


def test_not_on_conda():
    env = generate_environment("wants-beni", None, [Requirement("beni")])
    assert env["dependencies"] == [dict(pip=["flit", "beni"]), "python", "pip"]
