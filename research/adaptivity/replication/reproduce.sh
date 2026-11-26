#!/usr/bin/env bash
set -euo pipefail
umask 022
export PYTHONDONTWRITEBYTECODE=1 TZ=UTC PYTHONHASHSEED=17

if [[ $# != 3 ]]; then
    echo 'usage: bash reproduce.sh PINNED_EPFL PINNED_ISCAS NEW_RESULT_DIR' >&2
    exit 2
fi

replication=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
study=$(dirname -- "$replication")
repo=$(cd -- "$study/../.." && pwd)
if [[ -n "$(git -C "$repo" status --porcelain --untracked-files=all)" ]]; then
    echo 'use a clean study checkout' >&2
    exit 1
fi
mkdir -- "$3"
{
    git -C "$repo" rev-parse HEAD
    python3 --version
    node --version
    git --version
} > "$3/environment.txt"

bash "$study/replay.sh" "$1" "$3/a01"
node "$study/ec2.mjs" "$3/a01/inputs.json" > "$3/a01/ec2.json"
python3 "$study/audit.py" "$3/a01/inputs.json" "$3/a01/traces.json" "$3/a01/ec2.json" > "$3/a01/audit.json"
(cd -- "$3/a01" && sha256sum --check "$study/evidence/SHA256SUMS")

python3 "$replication/run.py" "$2" "$3/a02"
(cd -- "$3/a02" && sha256sum --check "$replication/evidence/SHA256SUMS")

(cd -- "$3" && sha256sum environment.txt a01/*.json a02/*.json > SHA256SUMS)
