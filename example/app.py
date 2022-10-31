"""Demo of interaction with Apalache using the `apalache-chai` client library.

This demo performs the following actions:

- Connects to a running apalche server
- Makes an RPC call to the server to parse a TLA file into a JSON representation
  of the model
- Updates the model to add some values taken from CLI args
- Makes an RPC call to the server to obtain counter-examples from the
  model-checker
- Produce a (crappy) graph showing the state transitions in the counter-examples
"""

import argparse
import asyncio
import collections.abc
import json
import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

import chai
import chai.blocking
import chai.client
from chai.cmd_executor import CheckingError, TlaModule

THIS_DIR = Path(os.path.dirname(os.path.realpath(__file__)))
MODEL_TLA_FILE = THIS_DIR / "FileSystem.tla"
APALACHE_DIR = THIS_DIR / ".." / "apalache"


def name_exp(name):
    """Construct a TLA string representing `name`"""
    return {
        "type": "Untyped",
        "kind": "ValEx",
        "value": {"kind": "TlaStr", "value": name},
    }


def int_exp(i):
    """Construct a TLA int of value `i`"""
    return {"kind": "TlaInt", "value": i}


def get_oper_by_name(model, name):
    """Find the operator named `name` in the `model`

    NOTE: Will crash with exception if the declaration doesn't exist
    """
    return next((d for d in model["modules"][0]["declarations"] if d["name"] == name))


def set_model_params(args, model):
    """Mutates the `model`, setting the values found in `args`"""

    # set the `Names` constant value, which is a set of names
    cinit = get_oper_by_name(model, "CInit")
    name_set = next(
        x for x in cinit["body"]["args"] if "oper" in x and x["oper"] == "SET_ENUM"
    )
    name_set["args"] = [name_exp(name) for name in args.names]

    # set the value of `MinPathLength` operator
    get_oper_by_name(model, "MinPathLength")["body"]["value"] = int_exp(
        args.path_length
    )

    # set the value of `MinDirSize` operator
    get_oper_by_name(model, "MinDirSize")["body"]["value"] = int_exp(args.dir_size)


def src_of_model(model):
    return chai.Source(json.dumps(model), format="json")


def immutable_trace_value(v):
    """
    Construct an immmutable version of a trace value
    """
    if isinstance(v, collections.abc.Hashable):
        return v
    elif isinstance(v, list):
        return tuple(immutable_trace_value(x) for x in v)
    elif isinstance(v, dict):
        if "#set" in v:
            return frozenset(immutable_trace_value(x) for x in v["#set"])
        elif "#tup" in v:
            return tuple(immutable_trace_value(x) for x in v["#tup"])
        else:
            # An immutable representation of a mapping
            # see https://stackoverflow.com/a/2704866/1187277
            return tuple(sorted((k, immutable_trace_value(v)) for k, v in v.items()))
    else:
        raise Exception(f"Could not make {v} immutable")


def hash_state(s: dict):
    """Hash a state based on its state variables, ignoring any meta data

    Enables a content-addressable graph node ID, so we can easily
    identify two equal states from different traces.
    """
    # Fresh copy of the state dict, with the meta field removed
    without_meta = {k: v for k, v in s.items() if k != "#meta"}
    return hash(immutable_trace_value(without_meta))


def build_state_graph(counter_examples):
    """Build a graph of all he states in the `counter_examples`"""
    # For info on graph construction, see
    # https://networkx.org/documentation/latest/reference/classes/digraph.html
    g = nx.DiGraph()
    for trace_n, trace in enumerate(counter_examples):
        last_id = 0
        for state_n, state in enumerate(trace["states"]):
            trace_index = f"({trace_n}:{state_n})"
            id = hash_state(state)
            node = g.nodes.get(id)
            if node is not None:
                node["traces"] = node["trace_indexes"].append(trace_index)
            else:
                g.add_node(id, **state)
                g.nodes[id]["trace_indexes"] = [trace_index]
            if last_id != 0:
                # Label the edge with the command
                cmd = immutable_trace_value(state["cmd"]["#tup"][0])
                g.add_edge(last_id, id, object=cmd)
            last_id = id
        else:
            # Reset last_id after finishing the trace
            last_id = 0

    return g


def save_state_graph(g, path):
    """Save the state graph as a png"""
    # For meanings of the params, see
    # https://networkx.org/documentation/latest/reference/drawing.html
    options = {
        "linewidths": 3,
        "arrows": True,
    }

    pos = nx.planar_layout(g)
    nx.draw(
        g,
        pos=pos,
        **options,
    )
    node_labels = {
        n: "\n".join(v) for n, v in nx.get_node_attributes(g, "trace_indexes").items()
    }
    nx.draw_networkx_labels(g, pos=pos, labels=node_labels, font_size=8)
    nx.draw_networkx_edge_labels(
        g, pos=pos, edge_labels=nx.get_edge_attributes(g, "object")
    )
    plt.savefig(path)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--names",
        help="which names can be used for forming file paths",
        type=lambda s: s.split(","),
        default=["foo", "bar", "baz"],
    )
    parser.add_argument(
        "--path-length",
        help="the system must include a path with at least this many components",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--dir-size",
        help="A directory with at least this many children must exist",
        type=int,
        default=2,
    )
    parser.add_argument(
        "--branches",
        help="the max paths to a suitable state that should be found",
        type=int,
        default=4,
    )
    return parser.parse_args()


async def main(args: argparse.Namespace):
    async with chai.ChaiCmdExecutor.create(timeout=5.0) as client:
        print("Connection to the Apalache server established")

        # Construct Apalache RPC input from a file
        # (will also load dependencies that can be found in the same
        # dir if needed).
        source = chai.Source.of_file_load_deps(MODEL_TLA_FILE)
        print(f"Source file loaded from {MODEL_TLA_FILE}")

        # Load the TLA into a JSON representation of the model
        model = await client.typecheck(source)
        # NOTE: Production imlementations should include proper error handling
        assert isinstance(model, TlaModule)
        print("Model parsed, typechecked, and loaded")

        # Use the CLI `args` to update parts of the model
        set_model_params(args, model)
        print("Model parameters updated from CLI params")

        # Run the typechecker to obtain counterexamples
        check_resp = await client.check(
            input=src_of_model(model),
            config={
                "checker": {
                    "cinit": "CInit",
                    "inv": ["Inv"],
                    "view": "View",
                    "max-error": args.branches,
                },
            },
        )
        # NOTE: Production imlementations should include proper error handling
        assert isinstance(check_resp, CheckingError)
        print("Counter examples have been obtained")

        # Generate and save a graph of the states from the counter examples
        img_path = Path("demo-states-graph.png")
        g = build_state_graph(check_resp.counter_example)
        save_state_graph(g, img_path)
        print(f"The state graph has been saved to {img_path}")


if __name__ == "__main__":
    try:
        asyncio.run(main(parse_args()))
    except chai.client.NoServerConnection:
        print("Could not connect to the Apalache server. Is it running?")
        sys.exit(1)
