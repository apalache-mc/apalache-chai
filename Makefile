##
# Chai

# Location of the protobuf files from Apalache
APALACHE_PROTO := apalache/shai/src/main/protobuf

update-grpc: transExplorer_pb2.py transExplorer_pb2_grpc.py

%_pb2.py %_pb2_grpc.py:
	python -m grpc_tools.protoc \
		--proto_path=$(APALACHE_PROTO)/  \
		--python_out=chai/ \
		--mypy_out=chai/ \
		--grpc_python_out=chai/ \
		--mypy_grpc_out=chai/ \
		$(APALACHE_PROTO)/$*.proto
