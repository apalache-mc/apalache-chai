##
# Chai

# Location of the protobuf files from Apalache
APALACHE_PROTO := apalache/shai/src/main/protobuf

# Location from which the protobuf files must be read
#
# If the proto file are not located in a directory called "chai", then the
# generated modules won't use absolute imports, which will break imports in
# the package.
#
# See this issue details: https://github.com/protocolbuffers/protobuf/issues/1491
CHAI_PROTO := proto/chai

update-grpc: chai/transExplorer_pb2.py chai/transExplorer_pb2_grpc.py chai/transExplorer_pb2.pyi chai/transExplorer_pb2_grpc.pyi

$(CHAI_PROTO):
	mkdir -p $(CHAI_PROTO)

$(CHAI_PROTO)/transExplorer.proto: $(CHAI_PROTO)
	cp $(APALACHE_PROTO)/transExplorer.proto proto/chai/transExplorer.proto

# The generated protobuf and gRPC code
#
# `--proto_path` will trim the matching the part of the path from the package
# names and imports of the generated code
#
# `--mypy_out` and `--mypy_grpc_out` ensure that type stubs will be generated
# for the generated protobuf and gRPC code
chai/%_pb2.py chai/%_pb2.pyi chai/%_pb2_grpc.py chai/%_pb2_grpc.pyi: $(CHAI_PROTO)/transExplorer.proto
	python -m grpc_tools.protoc \
		--proto_path=proto/  \
		--python_out=. \
		--mypy_out=. \
		--grpc_python_out=. \
		--mypy_grpc_out=. \
		$(CHAI_PROTO)/$*.proto
