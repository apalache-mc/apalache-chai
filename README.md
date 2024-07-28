# 🍵 Chai: Client for Human-Apalache Interaction

Chai is a Python RPC client to interact with the Server for Human-Apalache
Interaction (or *Shai*). It enables transparent interactions with the Apalache
model checker via python function calls.

Chai is developed by the [Apalache](https://apalache.informal.systems/) team at
[Informal Systems](https://informal.systems/).

## Installation

You can install the `apalache-chai` library from this git repo with:

```sh
pip install git+https://github.com/informalsystems/apalache-chai.git
```

If you are using [poetry](https://python-poetry.org/) to manage your project,
you can add a dependency on `apalache-chai` with:

```sh
poetry add git+https://github.com/informalsystems/apalache-chai.git
```

## Documentation

- [API Documentation](https://apalache-mc.github.io/apalache-chai/chai.html)
- [Example Application](./example/README.md)

## Development

### Clone the repository

``` sh
git clone --recurse-submodules git@github.com:informalsystems/apalache-chai.git
```

The `--recurse-submodules` flag is needed because we use a git submodule to
bring in the `.proto` files from Apalache.

### Dev Dependencies

#### Required

- [poetry](https://python-poetry.org/docs/master/#installing-with-the-official-installer)

#### Recommended

- [direnv](https://direnv.net/)

### Activate the development shell

```sh
poetry shell
```

### Updating the protobuf messages

To update he proto files, first update to the desired commit of the `apalache`
submodule, then regenerate the gRPC code, e.g.,

``` sh
pushd apalache && git pull && popod
make update-grpc
```

### Documentation

We use [`pdoc`](https://pdoc.dev/docs/pdoc.html) for generating our API docs.

You can run the doc server on the code base with

``` sh
poetry run pdoc ./chai
```

### Testing

#### Unit tests

Unit tests are defined in [./tests](./tests).

Run the unit tests (this also runs static analysis via `pyright`):

```sh
make test
```

#### Integration tests

##### Dependencies

- Ensure required version of Apalache is built by running `make apalache`.
- Source the [.envrc](./envrc) (automatic if you use `direnv`).
- [The nix package manager with flakes enabled](https://github.com/informalsystems/cosmos.nix#non-nixos)

The reason for depending on nix for our integration test is as follows: To run
the integration tests, we need the version of Apalache included as a git
submodule. We ensure the version is kept in sync by building the Apalache
executable from the exact same git submodule used to obtain the proto files.
Since we are building Apalache, we need to ensure that we have all build
dependencies. We therefore reuse Apalache's `flake.nix`, which is already
maintained and ensures pre-requisties are supplied.

##### Running

```sh
make integration
```
