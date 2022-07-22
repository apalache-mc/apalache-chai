# Chai: Client for Human-Apalache Interaction

Chai is a Python RPC client to interact with the (nascent) Server for
Human-palache Interaction (or *Shai*).

## Development

### Clone the repository

``` sh
git clone --recurse-submodules git@github.com:informalsystems/apalache-chai.git
```

The `--recurse-submodules` flag is needed because we use a git submodule to
bring in the `.proto` files from Apalache.

### Dev Dependencies

- [poetry](https://python-poetry.org/docs/master/#installing-with-the-official-installer)

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

### Integration tests

#### Dependencies

- [The nix package manager with flakes enabled](https://github.com/informalsystems/cosmos.nix#non-nixos)

The reason for depending on nix for our integration test is as follows: To run
the integration tests, we need the version of Apalache included as a git
submodule. We ensure the version is kept in sync by building the Apalache
executable from the git submodule we use to obtain the proto files, and to
ensure that we have all build dependencies for that build, we reuse Apalache's
`flake.nix`.
