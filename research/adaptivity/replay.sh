#!/usr/bin/env bash
set -euo pipefail
umask 022

if [[ $# != 2 ]]; then
    echo 'usage: bash replay.sh EPFL_CHECKOUT NEW_OUTPUT_DIRECTORY' >&2
    exit 2
fi

study_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
mkdir -- "$2"
export PYTHONDONTWRITEBYTECODE=1

metrics_path="$2/metrics.txt"
{
    python3 --version
    node --version
    git --version
} > "$metrics_path"
/usr/bin/time -f 'generate elapsed_s=%e peak_rss_kib=%M exit=%x' -a -o "$metrics_path" \
    python3 "$study_dir/generate.py" "$1" > "$2/inputs.json"
/usr/bin/time -f 'evaluate elapsed_s=%e peak_rss_kib=%M exit=%x' -a -o "$metrics_path" \
    node "$study_dir/evaluate.mjs" "$2/inputs.json" > "$2/traces.json"
/usr/bin/time -f 'decide elapsed_s=%e peak_rss_kib=%M exit=%x' -a -o "$metrics_path" \
    python3 "$study_dir/decide.py" "$2/inputs.json" "$2/traces.json" > "$2/decision.json"
