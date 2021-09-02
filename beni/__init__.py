"""
Generate environment.yml from pyproject.toml

"""


from __future__ import annotations

import argparse
import json
import typing
import urllib.request
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from enum import Enum, auto
from pathlib import Path
from shutil import copyfileobj
from urllib.parse import urlparse

import platformdirs
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


__version__ = "0.4.3"

CACHE_DIR = Path(platformdirs.user_cache_dir("beni"))
BASE_URL = "https://raw.githubusercontent.com/regro"
CF_GRAPH_URL = f"{BASE_URL}/cf-graph-countyfair/master/graph.json"
CF_MAPPING_URL = (
    f"{BASE_URL}/cf-graph-countyfair/master/mappings/pypi/name_mapping.yaml"
)


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


class CFMapping(typing.TypedDict):
    conda_name: str
    import_name: str
    mapping_source: str
    pypi_name: str


parser = argparse.ArgumentParser(__name__, description="Generate an environment.yml.")
parser.add_argument(
    "paths", metavar="pyproject.toml", type=Path, nargs="+", help="flit config files"
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
        "Which dependencies to emit. 'production' means no extras, "
        "'develop' means the extras 'test', 'doc', and 'dev', 'all' means all extras, "
        "and 'extras' means the ones specified in `--extras` or all extras if `--extras` is not specified."
    ),
)
extras_action = parser.add_argument(
    "--extras",
    metavar="extra1,...",
    default=(),
    type=lambda l: l.split(",") if l else (),
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


def get_cached(url: str, max_age: timedelta = timedelta(hours=1)) -> Path:
    parts = urlparse(url)
    cache_path = CACHE_DIR / parts.netloc / parts.path.lstrip("/")
    if cache_path.is_file():
        last_modified = datetime.fromtimestamp(cache_path.stat().st_mtime, timezone.utc)
        now = datetime.now(timezone.utc)
        if (now - last_modified) < max_age:
            return cache_path
        msg = f"Re-creating old cache for {cache_path.name}"
    else:
        cache_path.parent.mkdir(exist_ok=True, parents=True)
        msg = f"Creating cache for {cache_path.name} at {CACHE_DIR}"

    req = urllib.request.Request(url, headers={"User-Agent": "beni"})
    with urllib.request.urlopen(req) as resp, tqdm.tqdm.wrapattr(
        cache_path.open("wb"), "write", desc=msg, total=getattr(resp, "length", None)
    ) as f:
        copyfileobj(resp, f)
    return cache_path


class CondaForgeMapper:
    data: typing.List[CFMapping]
    """All non-trivial mappings between PyPI and Conda Forge packages"""

    cf_pkgs: typing.Set[str]
    """All Conda Forge package names"""

    _pypi2cf: typing.Dict[str, str]
    """A dict from normalized PyPI name to conda forge name"""

    def __init__(self):
        self.data = typing.cast(
            typing.List[CFMapping],
            yaml.safe_load(get_cached(CF_MAPPING_URL).read_bytes()),
        )
        self.cf_pkgs = {
            self._normalize(n["id"])
            for n in json.loads(get_cached(CF_GRAPH_URL).read_bytes())["nodes"]
        }
        self._pypi2cf = {
            self._normalize(m["pypi_name"]): m["conda_name"] for m in self.data
        }

    @staticmethod
    def _normalize(name: str) -> str:
        """Normalize a PyPI or Conda Forge package name into lower-case-with-dashes"""
        return name.casefold().replace("_", "-")

    def pypi2cf(self, pypi_name: str) -> typing.Optional[str]:
        """Get the name a PyPI package has in Conda Forge. None if it can’t be found."""
        norm_name = self._normalize(pypi_name)
        return self._pypi2cf.get(norm_name) or (
            norm_name if norm_name in self.cf_pkgs else None
        )


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

    mapper = CondaForgeMapper()
    for r in requirements:
        if (cf_name := mapper.pypi2cf(r.name)) is None:
            continue
        dependencies.add(f"{cf_name}{r.specifier}")

    return {
        "name": name,
        "channels": ["conda-forge"],
        "dependencies": [{"pip": ["flit"]}, *dependencies],
    }


def extras_to_install(
    c: flit_config.LoadedConfig, deps: Deps, extras: typing.Sequence[str]
) -> typing.Set[str]:
    to_install = set(extras)
    if any(
        (
            deps is Deps.all,
            deps is Deps.extras and not to_install,
            "all" in to_install,
        )
    ):
        to_install |= set(c.reqs_by_extra.keys())
    elif deps is Deps.develop:
        to_install |= {"dev", "doc", "test"}
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
        if (
            len(markers) < 3
            or not isinstance(markers[0], tuple)
            or not hasattr(markers[0][0], "value")
        ):
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
    first_module: typing.Optional[str] = None
    ignored_modules: typing.List[str] = args.ignore or []
    for path in args.paths:
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
    assert first_module is not None

    reqs_final = [r for r in requires if r.name not in ignored_modules]
    if args.format is Format.conda:
        env = generate_environment(first_module, python_version, reqs_final)
        spec = yaml.dump(env)
    elif args.format is Format.pip:
        spec = "\n".join(map(str, clear_extras(reqs_final)))
    else:
        assert False
    print(spec)
