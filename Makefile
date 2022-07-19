##
# Chai

# Location of the protobuf files from Apalache
APALACHE_PROTO := apalache/shai/src/main/protobuf
CHAI_PROTO := proto/chai

update-grpc: chai/transExplorer_pb2.py chai/transExplorer_pb2_grpc.py chai/transExplorer_pb2.pyi chai/transExplorer_pb2_grpc.pyi

$(CHAI_PROTO):
	mkdir -p $(CHAI_PROTO)

# If the proto file is not in a directory calle "chai", then the generated modules
# won't use absolute imports, which will then break imports in the package.
# See this mess: https://github.com/protocolbuffers/protobuf/issues/1491
$(CHAI_PROTO)/transExplorer.proto: $(CHAI_PROTO)
	cp $(APALACHE_PROTO)/transExplorer.proto proto/chai/transExplorer.proto

# The generated protobuf and gRPC code
chai/%_pb2.py chai/%_pb2.pyi chai/%_pb2_grpc.py chai/%_pb2_grpc.pyi: $(CHAI_PROTO)/transExplorer.proto
	python -m grpc_tools.protoc \
		--proto_path=proto/  \
		--python_out=. \
		--mypy_out=. \
		--grpc_python_out=. \
		--mypy_grpc_out=. \
		$(CHAI_PROTO)/$*.proto
