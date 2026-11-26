"""Read the pinned EPFL BLIF corpus and simulate deterministic stuck-at faults."""

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from hashlib import sha1, sha256
from pathlib import Path
import os
import subprocess

UPSTREAM_COMMIT = "82d8cc6910419298e713a46644ed59fd3df53038"
PANELS = ("arithmetic", "random_control")


@dataclass(frozen=True, slots=True)
class Gate:
    destination: int
    # A cube stores positive and negative input indices. Omitted inputs are don't-care.
    cubes: tuple[tuple[tuple[int, ...], tuple[int, ...]], ...]
    on_set: bool


@dataclass(frozen=True, slots=True)
class Circuit:
    inputs: tuple[str, ...]
    nodes: tuple[str, ...]
    output_slots: tuple[int, ...]
    gates: tuple[Gate, ...]

    def simulate(
        self, input_bits: Sequence[int], faults: Sequence[tuple[str, int]]
    ) -> tuple[str, ...]:
        """Return full output vectors for healthy lane 0 and one lane per fault."""
        if len(input_bits) != len(self.inputs) or any(not is_bit(bit) for bit in input_bits):
            raise ValueError("invalid primary input vector")
        if len(faults) > 7 or len(set(faults)) != len(faults):
            raise ValueError("invalid stuck-at fault list")
        if any(not is_bit(bit) for _, bit in faults):
            raise ValueError("invalid stuck-at bit")

        # A circuit is topologically ordered and each gate drives one distinct slot.
        # Packing models in lanes shares traversal while keeping their truth values separate.
        lane_count = len(faults) + 1
        all_lanes = (1 << lane_count) - 1
        slot_of = {}
        requested_nodes = {node for node, _ in faults}
        if requested_nodes:
            for name, gate in zip(self.nodes, self.gates, strict=True):
                if name in requested_nodes:
                    slot_of[name] = gate.destination
            if slot_of.keys() != requested_nodes:
                raise ValueError("fault does not target a .names output")

        set_one: dict[int, int] = {}
        set_zero: dict[int, int] = {}
        for lane, (node, bit) in enumerate(faults, 1):
            forces = set_one if bit else set_zero
            slot = slot_of[node]
            forces[slot] = forces.get(slot, 0) | (1 << lane)

        values = [all_lanes if bit else 0 for bit in input_bits]
        for gate in self.gates:
            covered = 0
            for positive, negative in gate.cubes:
                match = all_lanes
                for slot in positive:
                    match &= values[slot]
                for slot in negative:
                    match &= ~values[slot]
                covered |= match
            value = covered if gate.on_set else all_lanes ^ covered
            value |= set_one.get(gate.destination, 0)
            value &= ~set_zero.get(gate.destination, 0)
            values.append(value)

        return tuple(
            "".join("1" if values[slot] & (1 << lane) else "0" for slot in self.output_slots)
            for lane in range(lane_count)
        )


def is_bit(value: int) -> bool:
    return type(value) is int and value in (0, 1)


def logical_lines(source: str) -> Iterator[tuple[int, list[str]]]:
    pending: list[str] = []
    first_line = None
    for number, original in enumerate(source.splitlines(), 1):
        line = original.split("#", 1)[0].strip()
        if not line:
            continue
        if first_line is None:
            first_line = number
        continued = line.endswith("\\")
        payload = line[:-1] if continued else line
        if "\\" in payload:
            raise ValueError(f"line {number}: stray continuation marker")
        pending.extend(payload.split())
        if not continued:
            yield first_line, pending
            pending = []
            first_line = None
    if first_line is not None:
        raise ValueError(f"line {first_line}: unfinished continuation")


def make_gate(destination: int, fanins: list[int], table: list[list[str]]) -> Gate:
    cubes = []
    polarities = set()
    for row in table:
        if not fanins and len(row) == 1:
            pattern, polarity = "", row[0]
        elif fanins and len(row) == 2:
            pattern, polarity = row
        else:
            raise ValueError("malformed .names truth row")
        if len(pattern) != len(fanins) or set(pattern) - set("01-") or polarity not in ("0", "1"):
            raise ValueError("malformed .names cube")
        polarities.add(polarity)
        cubes.append((
            tuple(slot for slot, symbol in zip(fanins, pattern, strict=True) if symbol == "1"),
            tuple(slot for slot, symbol in zip(fanins, pattern, strict=True) if symbol == "0"),
        ))
    if len(polarities) > 1:
        raise ValueError("mixed on-set/off-set truth table")
    # Empty cover means constant 0. A nonempty off-set complements the matched cubes.
    return Gate(destination, tuple(cubes), polarities != {"0"})


def parse_blif(source: str) -> Circuit:
    """Parse the single-model, topologically ordered combinational BLIF subset."""
    lines = iter(logical_lines(source))

    def header(expected: str) -> list[str]:
        _, fields = next(lines, (0, []))
        if len(fields) < 2 or fields[0] != expected:
            raise ValueError(f"missing {expected} header")
        return fields[1:]

    if len(header(".model")) != 1:
        raise ValueError("invalid .model header")
    inputs = header(".inputs")
    outputs = header(".outputs")
    if len(set(inputs)) != len(inputs) or len(set(outputs)) != len(outputs):
        raise ValueError("duplicate port")
    if any(port.startswith(".") or "|" in port for port in [*inputs, *outputs]):
        raise ValueError("invalid port name")

    slots = {signal: slot for slot, signal in enumerate(inputs)}
    nodes = []
    gates = []
    current: tuple[list[int], str] | None = None
    table: list[list[str]] = []

    def flush_gate() -> None:
        if current is not None:
            fanins, node = current
            destination = len(slots)
            gates.append(make_gate(destination, fanins, table))
            nodes.append(node)
            slots[node] = destination
            table.clear()

    for number, fields in lines:
        if fields[0].startswith("."):
            flush_gate()
            match fields:
                case [".end"]:
                    if next(lines, None) is not None:
                        raise ValueError("data after .end")
                    if any(output not in slots for output in outputs):
                        raise ValueError("undriven primary output")
                    return Circuit(
                        tuple(inputs), tuple(nodes), tuple(slots[output] for output in outputs),
                        tuple(gates),
                    )
                case [".names", *fanins, node]:
                    if node in slots or node.startswith(".") or "|" in node:
                        raise ValueError(f"line {number}: invalid or multiply driven .names output")
                    if any(signal not in slots for signal in fanins):
                        raise ValueError(f"line {number}: undriven or forward .names input")
                    current = ([slots[signal] for signal in fanins], node)
                case _:
                    raise ValueError(f"line {number}: unsupported BLIF directive")
        elif current is None:
            raise ValueError(f"line {number}: truth row outside .names")
        else:
            table.append(fields)
    raise ValueError("missing .end directive")


def source_git(path: str | Path, *arguments: str) -> bytes:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_NO_REPLACE_OBJECTS="1",
               GIT_NO_LAZY_FETCH="1", GIT_ALLOW_PROTOCOL="", GIT_TERMINAL_PROMPT="0")
    return subprocess.run(["git", "-C", str(path), *arguments], env=env, check=True,
                          capture_output=True, timeout=30).stdout


def load_sources(path: str | Path) -> Iterator[tuple[str, str, Circuit]]:
    """Load corpus bytes from Git objects and record their SHA-256 digests."""
    if source_git(path, "rev-parse", "HEAD").decode("ascii").strip() != UPSTREAM_COMMIT:
        raise ValueError("EPFL checkout is not at the pinned commit")
    tree = source_git(path, "ls-tree", "-rz", "--full-tree", UPSTREAM_COMMIT, "--", *PANELS)
    sources = {}
    for entry in tree.split(b"\0")[:-1]:
        stat, raw_name = entry.split(b"\t", 1)
        mode, kind, oid = stat.decode("ascii").split()
        name = raw_name.decode("ascii")
        parts = name.split("/")
        if len(parts) == 2 and parts[0] in PANELS and name.endswith(".blif"):
            if mode not in ("100644", "100755") or kind != "blob":
                raise ValueError(f"{name}: expected regular Git blob")
            sources[name] = oid
    if any(sum(name.startswith(f"{panel}/") for name in sources) != 10 for panel in PANELS):
        raise ValueError("unexpected count of EPFL source files")

    for name in sorted(sources):
        data = source_git(path, "cat-file", "blob", sources[name])
        git_blob = f"blob {len(data)}\0".encode("ascii") + data
        if sha1(git_blob, usedforsecurity=False).hexdigest() != sources[name]:
            raise ValueError(f"{name}: Git blob digest mismatch")
        try:
            circuit = parse_blif(data.decode("ascii"))
        except ValueError as error:
            raise ValueError(f"{name}: {error}") from error
        yield name, sha256(data).hexdigest(), circuit
