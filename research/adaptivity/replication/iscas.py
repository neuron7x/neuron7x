"""Strict scalar simulator for the pinned structural ISCAS85 gate netlists."""
import hashlib
import re
import sys
from dataclasses import dataclass
from graphlib import TopologicalSorter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from epfl import source_git

UPSTREAM = "58539b81d9c622a6b55a4cabde5d6b1288b9fe1e"
PROTOCOL = "3678ad2bbf24badefa7f775e12789a8a7ab1aaa0"
CIRCUITS = ("c17", "c432", "c499", "c880", "c1355", "c1908", "c2670", "c3540",
            "c5315", "c6288", "c7552")
IDENTIFIER = r"[a-zA-Z_][a-zA-Z0-9_]*"
OPERATIONS = {
    "and": all, "or": any, "nand": lambda bits: not all(bits), "nor": lambda bits: not any(bits),
    "xor": lambda bits: sum(bits) % 2, "buf": lambda bits: bits[0], "not": lambda bits: not bits[0],
}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def names(content, *, distinct=True):
    result = tuple(name.strip() for name in content.split(","))
    require(all(re.fullmatch(IDENTIFIER, name) for name in result), "invalid signal")
    require(not distinct or len(result) == len(set(result)), "duplicate signal")
    return result


@dataclass(frozen=True)
class Circuit:
    inputs: tuple
    outputs: tuple
    nodes: tuple
    gates: tuple

    def simulate(self, input_bits, faults):
        require(len(input_bits) == len(self.inputs) and
                all(type(bit) is int and bit in (0, 1) for bit in input_bits), "invalid input bits")
        require(len(faults) <= 7 and len(set(faults)) == len(faults) and
                all(node in self.nodes and type(bit) is int and bit in (0, 1) for node, bit in faults),
                "invalid fault model")
        predictions = []
        for fault_node, fault_bit in ((None, None), *faults):
            values = dict(zip(self.inputs, input_bits, strict=True))
            for node, gate, fanins in self.gates:
                values[node] = fault_bit if node == fault_node else gate([values[name] for name in fanins])
            predictions.append("".join(str(int(values[output])) for output in self.outputs))
        return tuple(predictions)


def parse(source, expected_name):
    text = re.sub(r"//[^\n]*", "", source).strip()
    require(text.endswith("endmodule"), "missing endmodule")
    statements = [statement.strip() for statement in text[:-len("endmodule")].split(";")]
    require(len(statements) > 3 and statements[-1] == "", "invalid statement list")
    module = re.fullmatch(rf"module\s+({IDENTIFIER})\s*\(([^()]*)\)", statements[0])
    require(module is not None and module[1] == expected_name, "invalid module")

    declarations = {}
    instances = set()
    nodes = {}
    for statement in statements[1:-1]:
        decl = re.fullmatch(r"(input|output|wire)\s+([^()]+)", statement)
        if decl:
            require(not nodes and decl[1] not in declarations, "invalid declaration order")
            declarations[decl[1]] = names(decl[2])
            continue
        gate = re.fullmatch(rf"({'|'.join(OPERATIONS)})\s+({IDENTIFIER})\s*\(([^()]*)\)", statement)
        require(gate is not None and gate[2] not in instances, "invalid gate instance")
        node, *fanins = names(gate[3], distinct=False)
        require(len(fanins) == 1 if gate[1] in ("not", "buf") else len(fanins) >= 2, "invalid gate arity")
        require(node not in nodes, "multiple drivers")
        nodes[node] = (OPERATIONS[gate[1]], fanins)
        instances.add(gate[2])

    inputs, outputs = declarations["input"], declarations["output"]
    wires = declarations.get("wire", ())
    require(set(names(module[2])) == set(inputs + outputs), "inconsistent module port order")
    require(len(set((*inputs, *outputs, *wires))) == len(inputs) + len(outputs) + len(wires),
            "conflicting signal declarations")
    require(set(nodes) <= set((*outputs, *wires)) and set(outputs) <= set(nodes),
            "undriven output or undeclared gate")
    require(all(all(pin in nodes or pin in inputs for pin in pins) for _, pins in nodes.values()),
            "undriven gate input")

    order = TopologicalSorter({node: [pin for pin in pins if pin in nodes]
                              for node, (_, pins) in nodes.items()}).static_order()
    gates = tuple((node, *nodes[node]) for node in order)
    return Circuit(inputs, outputs, tuple(nodes), gates)


def load_sources(source):
    require(source_git(source, "rev-parse", "HEAD").decode().strip() == UPSTREAM, "wrong ISCAS commit")
    base = "logikbench/benchmarks/iscas85"
    for circuit in CIRCUITS:
        path = f"{base}/{circuit}/rtl/{circuit}.v"
        metadata = source_git(source, "ls-tree", "--full-tree", UPSTREAM, "--", path).decode().strip()
        oid = re.fullmatch(rf"100(?:644|755) blob ([0-9a-f]{{40}})\t{re.escape(path)}", metadata)
        require(oid is not None, f"missing regular source blob {path}")
        data = source_git(source, "cat-file", "blob", oid[1])
        blob = f"blob {len(data)}\0".encode() + data
        require(hashlib.sha1(blob, usedforsecurity=False).hexdigest() == oid[1], "ISCAS blob hash mismatch")
        yield path, oid[1], hashlib.sha256(data).hexdigest(), parse(data.decode("ascii"), circuit)
