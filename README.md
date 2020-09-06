# `beni`



[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black) ![.github/workflows/pythonpackage.yml](https://github.com/Quansight-Labs/beni/workflows/.github/workflows/pythonpackage.yml/badge.svg) [![PyPi Package](https://img.shields.io/pypi/v/beni)](https://pypi.org/project/beni/)


> *Common names: Bolivian anaconda, **Beni** anaconda*
>
> [Eunectes beniensis](https://en.wikipedia.org/wiki/Eunectes_beniensis) is a non-venomous boa species known only from the northeastern parts of Bolivia.
>
> The four-metre long Eunectes beniensis was initially believed to be the result of hybridization between green and yellow anacondas, but was later determined to be a distinct species. The taxonomic status is not clear, due to lack of information and the appearance similarity to Eunectes notaeus. It is closely related to Eunectes notaeus and Eunectes deschauenseei.

*`beni` is [`flit`](https://github.com/takluyver/flit) + [`conda`](https://docs.conda.io/en/latest/)*

## What?

This is a specific tool to fascilitate one workflow of using flit and conda together. The assumptions are:

1. You have a repository with at least one Python package
2. You use `flit` and `pyproject.toml` to describe your dependencies
3. You want to use Conda to manage local development but you wanna release your package on PyPi.
4. You want to generate an `environment.yml` for local development that will install as many of your Pypi dependencies through Conda as possible.

Without this tool you have to manually keep your `environment.yml` up to date with all your `pyproject.toml` files, which is error prone and time consuming.

## Unsolved issues

1. What if the conda forge name is different than the pypi name? We should keep a list of these mappings.
2. How do we use the `pyproject.toml` to automatically generate a conda forge recipe?
3. In the future could conda just read from the `pyproject.toml` file in some way to create an environment out of it?

## Usage

1. `pip install beni`
2. Run `beni <path to pyproject.toml> [<another path to pyproject.toml>] > binder/environment.yml` to generate an environment file. It adds all your requirements that are conda forge packages to this environment and names it after the first `pyproject.toml` module.
   each of your requirements to see if there is an equivalent conda forge package
3. Add `conda env create -f bind/environment.yml && conda activate <module name> && flit install --symlink` to your README as the dev setup.

## Example

```bash
$ beni -h
usage: beni [-h] [--deps {all,production,develop,extras}] [--extras extra1,...]
            [--ignore [foo [bar ...]]]
            pyproject.toml [pyproject.toml ...]

Generate an environment.yml.

positional arguments:
  pyproject.toml        flit config files

optional arguments:
  -h, --help            show this help message and exit
  --deps {all,production,develop,extras}
                        Which dependencies to emit. 'develop' means the extras 'test', 'doc', and 'dev',
                        'all' means all extras, and 'extras' means the ones specified in `--extras` or all
                        extras if `--extras` is not specified.
  --extras extra1,...   Install the dependencies of these (comma separated) extras additionally to the ones
                        implied by --deps. --extras=all can be useful in combination with --deps=production.
  --ignore [foo [bar ...]]
                        Conda packages to ignore

$ cat pyproject.toml
[tool.flit.metadata]
requires = [
    "typing_extensions",
    "typing_inspect",
    "python-igraph=0.8.0"
]
requires-python = ">=3.7"
[tool.flit.metadata.requires-extra]
test = [
    "pytest",
    "pytest-cov",
    "pytest-mypy",
    "pytest-randomly",
    "pytest-xdist",
    "pytest-testmon",
    "pytest-pudb",
    "mypy"
]
doc = [
    "sphinx",
    "sphinx-autodoc-typehints",
    "sphinx_rtd_theme",
    'recommonmark',
    "nbsphinx",
    "ipykernel",
    "IPython",
    "sphinx-autobuild"
]
dev = [
    "jupyterlab>=1.0.0",
    "nbconvert",
    "pudb"
]

$ beni pyproject.toml
name: metadsl
channels:
  - conda-forge
dependencies:
  - python>=3.7
  - pip
  - pip:
    - flit
  - typing_extensions
  - typing_inspect
  - python-igraph=0.8.0
  - pytest
  - pytest-cov
  - pytest-mypy
  - pytest-randomly
  - pytest-xdist
  - pytest-testmon
  - pytest-pudb
  - mypy
  - jupyterlab>=1.0.0
  - nbconvert
  - pudb
```

## Development

```bash
conda env create -f environment.yml
conda activate beni
flit install --symlink
```
