"""
Generate environment.yml from pyproject.toml

"""


from __future__ import annotations

import argparse
import http.client
import typing
from copy import deepcopy
from enum import Enum, auto
from pathlib import Path

import tqdm
import typeguard
import yaml
from packaging.requirements import Requirement
try:
    import flit_core.config as flit_config
    flit2 = False
except ImportError:
    import flit_core.inifile as flit_config
    flit2 = True


__version__ = "0.4.2"


class Format(Enum):
    pip = auto()
    conda = auto()

    def __str__(self):
        return self.name


class Deps(Enum):
    all = auto()
    production = auto()
    develop = auto()
    extras = auto()

    def __str__(self):
        return self.name


parser = argparse.ArgumentParser(__name__, description="Generate an environment.yml.")
parser.add_argument(
    "paths", metavar="pyproject.toml", type=Path, nargs="+", help="flit config files",
)
parser.add_argument(
    "--format",
    "-f",
    default=Format.conda,
    type=Format.__getitem__,
    choices=Format,
    help="The format of the dependency file. “pip” means PEP 508, “conda” means environment.yml",
)
parser.add_argument(
    "--deps",
    default=Deps.extras,
    type=Deps.__getitem__,
    choices=Deps,
    help=(
        "Which dependencies to emit. 'develop' means the extras 'test', 'doc', and 'dev', 'all' means all extras, "
        "and 'extras' means the ones specified in `--extras` or all extras if `--extras` is not specified."
    ),
)
extras_action = parser.add_argument(
    "--extras",
    metavar="extra1,...",
    default=(),
    type=lambda l: l.split(',') if l else (),
    help=(
        "Install the dependencies of these (comma separated) extras additionally to the ones implied by --deps. "
        "--extras=all can be useful in combination with --deps=production."
    ),
)
parser.add_argument(
    "--ignore",
    metavar=("foo", "bar"),
    type=str,
    nargs="*",
    help="Conda packages to ignore",
)


def is_conda_forge_package(name: str) -> bool:
    """
    Checks if something is a conda forge package by hitting conda page.

    If 200 then package, if 302 then not.
    """
    # Have to use http.client instead of urllib b/c no way to disable redirects
    # on urrlib and it's wasteful to follow (AFAIK)

    # Need user agent or else got unauthorized
    conn = http.client.HTTPSConnection("anaconda.org")
    conn.request("GET", f"/conda-forge/{name}/", headers={"User-Agent": "beni"})
    r = conn.getresponse()
    conn.close()
    return r.status == 200


class Environment(typing.TypedDict):
    name: str
    channels: typing.List[str]
    dependencies: typing.List[typing.Union[str, typing.Dict[str, typing.List[str]]]]


@typeguard.typechecked
def generate_environment(
    name: str,
    python_version: typing.Optional[str],
    requirements: typing.List[Requirement],
) -> Environment:
    dependencies = {"pip"}

    if python_version:
        dependencies.add(f"python{python_version}")
    else:
        dependencies.add("python")

    for r in tqdm.tqdm(requirements, desc="Checking packages"):
        if not is_conda_forge_package(r.name):
            continue
        dependencies.add(f"{r.name}{r.specifier}")

    return {
        "name": name,
        "channels": ["conda-forge"],
        "dependencies": [{"pip": ["flit"]}, *dependencies],
    }


def extras_to_install(c: flit_config.LoadedConfig, deps: Deps, extras: typing.Sequence[str]) -> typing.Set[str]:
    to_install = set(extras)
    if any((
        deps is Deps.all,
        deps is Deps.extras and not to_install,
        'all' in to_install,
    )):
        to_install |= set(c.reqs_by_extra.keys())
    elif deps is Deps.develop:
        to_install |= {'dev', 'doc', 'test'}
    return to_install


def is_in_extras(req: Requirement, extras: typing.Set[str]):
    if not req.marker:
        return True
    for extra in extras:
        if req.marker.evaluate(dict(extra=extra)):
            return True
    return False


def clear_extras(reqs: typing.Iterable[Requirement]):
    reqs_no_extra = [deepcopy(r) for r in reqs]
    for r in reqs_no_extra:
        if r.marker is None:
            continue
        markers = getattr(r.marker, "_markers", [])
        if len(markers) < 3 or not isinstance(markers[0], tuple) or not hasattr(markers[0][0], "value"):
            # Either empty or they changed the code
            r.marker = None
        elif len(markers) == 1 and markers[0][0].value == "extra":
            # Just an extra
            r.marker = None
        elif markers[0][0].value == "extra" and markers[1] == "and":
            # Extra at the start
            r.marker._markers[:2] = []
        elif markers[-2] == "and" and markers[-1][0].value == "extra":
            # Extra at the end
            r.marker._markers[-2:] = []
    return reqs_no_extra


def main(argv: typing.Optional[typing.Sequence[str]] = None) -> None:
    args = parser.parse_args(argv)
    python_version: typing.Optional[str] = None
    requires: typing.List[Requirement] = []
    first_module = None
    ignored_modules: typing.List[str] = args.ignore or []
    for path in tqdm.tqdm(args.paths, desc="Parsing configs"):
        c = flit_config.read_flit_config(str(path) if flit2 else path)
        if not first_module:
            first_module = c.module
        ignored_modules.append(c.module)
        metadata = c.metadata
        extras = extras_to_install(c, args.deps, args.extras)
        if "requires_python" in metadata:
            python_version = metadata["requires_python"]
        if "requires_dist" in metadata:
            reqs = map(Requirement, metadata["requires_dist"])
            reqs_filtered = filter(lambda req: is_in_extras(req, extras), reqs)
            requires.extend(reqs_filtered)

    reqs_final = [r for r in requires if r.name not in ignored_modules]
    if args.format is Format.conda:
        env = generate_environment(first_module, python_version, reqs_final)
        spec = yaml.dump(env)
    elif args.format is Format.pip:
        spec = '\n'.join(map(str, clear_extras(reqs_final)))
    else:
        assert False
    print(spec)
