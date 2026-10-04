#!/usr/bin/env python3
"""Summarize an exported nsys CUDA SQLite trace; durations are work, not fps."""
import argparse
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqlite", type=Path)
    parser.add_argument("--frames", type=int, required=True, help="actual encoded frame count")
    parser.add_argument("--output", type=Path, help="new JSON file; otherwise stdout")
    args = parser.parse_args(argv)
    if args.frames <= 0:
        parser.error("--frames must be positive")
    path = args.sqlite.resolve(strict=True)
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    def cols(table):
        return {row[1] for row in db.execute('PRAGMA table_info("' + table + '")')}

    def measure(count=0, ns=0, nbytes=None):
        value = {"count": count, "total_ms": ns / 1e6,
                 "ms_per_declared_frame": ns / 1e6 / args.frames}
        if nbytes is not None:
            value.update(bytes=nbytes, bytes_per_declared_frame=nbytes / args.frames)
        return value

    def category(name):
        for pattern, group in [("kernel_fgs_bilateral", "bilateral"),
                               ("kernel_fgs_flat_metrics", "flat_metrics"),
                               ("kernel_fgs_chroma_source_metrics", "flat_metrics"),
                               ("kernel_fgs_detail", "temporal_detail_metrics"),
                               ("kernel_fgs_motion_confidence", "temporal_detail_metrics"),
                               ("kernel_fgs_scene_sad", "temporal_detail_metrics"),
                               ("kernel_fgs_model_stats", "model_stats")]:
            if pattern in name:
                return group
        return "other"

    kernel = "CUPTI_ACTIVITY_KIND_KERNEL"
    if not {kernel, "StringIds"} <= tables or not {"start", "end"} <= cols(kernel):
        parser.error("SQLite lacks required nsys kernel/StringIds tables or timestamps")
    name_col = next((c for c in ("demangledName", "shortName", "mangledName") if c in cols(kernel)), None)
    if name_col is None:
        parser.error("kernel schema has no supported name column")
    rows = db.execute(f'''SELECT COALESCE(s.value, 'unknown:' || k.{name_col}),
        COUNT(*), SUM(k.end-k.start) FROM {kernel} k
        LEFT JOIN StringIds s ON s.id=k.{name_col} GROUP BY 1''').fetchall()
    if not rows:
        parser.error("SQLite contains no CUDA kernel events")
    groups = {name: [0, 0] for name in
              ("bilateral", "flat_metrics", "temporal_detail_metrics", "model_stats", "other")}
    per_kernel = []
    fgs = [0, 0]
    for name, count, ns in rows:
        group = category(name)
        groups[group][0] += count
        groups[group][1] += ns
        if "kernel_fgs_" in name:
            fgs[0] += count
            fgs[1] += ns
        per_kernel.append({"name": name, "group": group, **measure(count, ns)})
    warnings = []
    report = {"sqlite": str(path), "declared_frames": args.frames,
              "schema": {t: sorted(cols(t)) for t in sorted(tables)
                         if t.startswith("CUPTI_ACTIVITY_KIND_") or t in ("StringIds", "ENUM_CUDA_MEMCPY_OPER")},
              "kernel_total": measure(sum(v[0] for v in groups.values()), sum(v[1] for v in groups.values())),
              "fgs_kernel_total": measure(*fgs),
              "kernel_groups": {k: measure(*v) for k, v in groups.items()},
              "kernels": sorted(per_kernel, key=lambda r: r["total_ms"], reverse=True),
              "warnings": warnings,
              "notes": ["Durations are sums of CUDA activities divided by the supplied frame count; startup/drain are included.",
                        "Kernel/copy activities may overlap; totals are not elapsed time or an fps prediction.",
                        "Host synchronization API durations include overhead and waiting; do not add them to GPU work as independent latency.",
                        "A shared GPU can change individual kernel durations; compare repeated alternating traces."]}
    for column in ("globalPid", "deviceId"):
        if column in cols(kernel):
            report[column + "s"] = [r[0] for r in db.execute(f"SELECT DISTINCT {column} FROM {kernel}")]
    if len(report.get("globalPids", [])) > 1:
        warnings.append("Trace contains multiple CUDA process identifiers; ensure all belong to the profiled job.")

    runtime = "CUPTI_ACTIVITY_KIND_RUNTIME"
    report["host_synchronization"] = {"available": runtime in tables}
    if runtime in tables:
        where = "WHERE r.callchainId IS NULL" if "callchainId" in cols(runtime) else ""
        api_rows = db.execute(f'''SELECT s.value, COUNT(*), SUM(r.end-r.start)
            FROM {runtime} r JOIN StringIds s ON s.id=r.nameId {where} GROUP BY 1''')
        apis = {"cudaStreamSynchronize": [0, 0], "cudaEventSynchronize": [0, 0], "cudaDeviceSynchronize": [0, 0]}
        for name, count, ns in api_rows:
            for api, values in apis.items():
                if name == api or name.startswith(api + "_"):
                    values[0] += count
                    values[1] += ns
        report["host_synchronization"].update({k: measure(*v) for k, v in apis.items()})

    memcpy = "CUPTI_ACTIVITY_KIND_MEMCPY"
    have_copy = memcpy in tables and {"copyKind", "start", "end", "bytes"} <= cols(memcpy)
    enum = "ENUM_CUDA_MEMCPY_OPER"
    labels = dict(db.execute(f"SELECT id,label FROM {enum}")) if enum in tables else {}
    report["memcpy"] = {"available": have_copy, "direction_labels_available": bool(labels)}
    if have_copy:
        copies = defaultdict(lambda: [0, 0, 0])
        per_kind = []
        for kind, count, ns, nbytes in db.execute(f"SELECT copyKind,COUNT(*),SUM(end-start),SUM(bytes) FROM {memcpy} GROUP BY copyKind"):
            label = labels.get(kind, "unknown:" + str(kind))
            normalized = re.sub("[^a-z0-9]", "", label.lower())
            direction = {"htod": "H2D", "h2d": "H2D", "hosttodevice": "H2D",
                         "dtoh": "D2H", "d2h": "D2H", "devicetohost": "D2H",
                         "dtod": "D2D", "d2d": "D2D", "devicetodevice": "D2D"}.get(normalized, "other")
            for index, value in enumerate((count, ns, nbytes)):
                copies[direction][index] += value
            per_kind.append({"copy_kind": kind, "label": label, **measure(count, ns, nbytes)})
        report["memcpy"].update(total=measure(*(sum(v[i] for v in copies.values()) for i in range(3))),
                                directions={k: measure(*copies[k]) for k in ("H2D", "D2H", "D2D", "other")},
                                kinds=per_kind)
    db.close()
    output = json.dumps(report, indent=2) + "\n"
    if args.output:
        with args.output.open("x") as handle:
            handle.write(output)
    else:
        print(output, end="")
    return report


if __name__ == "__main__":
    main()
