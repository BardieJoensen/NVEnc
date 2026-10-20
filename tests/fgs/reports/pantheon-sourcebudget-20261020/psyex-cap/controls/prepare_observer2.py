#!/usr/bin/env python3
"""Fresh observer-only correction; preserve the original policy source/build."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / "worker/psyex-r18-cap/source"
NEW = HERE / "source-observer-2"
OUT = HERE / "observer-freeze-2"
MANIFEST = HERE / "source-freeze-1/source-manifest.json"
EXPECTED = "f405193d6b35d74919d452457e9b8c93e52938ebbf184dda07c7622180af75ca"


def ident(path):
    with path.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    return dict(path=str(path.resolve()), size=path.stat().st_size, sha256=digest)


def manifest(root):
    rows = []
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if ".git" in rel.parts:
            continue
        assert not p.is_symlink()
        if p.is_file():
            row = ident(p)
            rows.append([str(rel), row["size"], row["sha256"]])
    return rows


def replace(name, old, new):
    p = NEW / "Source/Lib/Codec" / name
    text = p.read_text()
    assert text.count(old) == 1, name
    p.write_text(text.replace(old, new))


def main():
    assert ident(MANIFEST)["sha256"] == EXPECTED
    before = manifest(OLD)
    assert before == json.loads(MANIFEST.read_text())
    assert not NEW.exists() and not OUT.exists()
    shutil.copytree(OLD, NEW)
    old_prelude = """    if (pb_r18_is_active() && sb < 510 && ctx && dest && src) {
        EncDecContext *r18ed = ctx;
        BlkStruct *r18b = r18ed->blk_ptr;
        unsigned r18off = 0;
        REQUIRE(r18ed->blk_geom && r18b && r18b->tx_depth < MAX_TX_DEPTH);
        for (unsigned r18t = 0; r18t < r18ed->blk_geom->txb_count[r18b->tx_depth]; ++r18t)
            r18off += r18ed->blk_geom->tx_width[r18b->tx_depth] * r18ed->blk_geom->tx_height[r18b->tx_depth];
        REQUIRE(r18ed->coded_area_sb >= r18off);
        pb_r18_final_commit(pcs,ctx,sb,ordinal,dest,src,r18ed->coded_area_sb-r18off);
    }
"""
    replace("pc_impl.h", old_prelude,
            "    pb_r18_final_commit(pcs,ctx,sb,ordinal,dest,src);\n")
    replace("pb_trace.h", "                         const void *, const void *, unsigned);",
            "                         const void *, const void *);")
    replace("pb_trace.c", '#include "sequence_control_set.h"\n',
            '#include "sequence_control_set.h"\n#include "utility.h"\n')
    replace("pb_trace.c", "                         const void *dest, const void *src, unsigned offset) {",
            "                         const void *dest, const void *src) {")
    replace("pb_trace.c",
            "    REQUIRE(g && b->tx_depth < MAX_TX_DEPTH);\n    unsigned n = g->txb_count[b->tx_depth]; REQUIRE(n <= MAX_TXB_COUNT);\n",
            """    REQUIRE(g && b->tx_depth < MAX_TX_DEPTH);
    /* EncDec's later CDF-update cursor may stay zero. Derive this final
       block's coefficient-layout start from its committed predecessors.
       This array prefix belongs to this SB and this attempt; no cross-frame
       observer state or encoder state is written. Actual TU offsets remain
       independently observed on the encoding path. */
    REQUIRE(ordinal < 256 && d == &s->final_blk_arr[ordinal]);
    unsigned offset = 0;
    for (unsigned prior = 0; prior < ordinal; ++prior) {
        const EcBlkStruct *committed = &s->final_blk_arr[prior];
        REQUIRE(committed->mds_idx < pcs->scs->max_block_cnt);
        const BlockGeom *pg = get_blk_geom_mds(committed->mds_idx);
        REQUIRE(pg && pg->bwidth && pg->bheight);
        offset += pg->bwidth * pg->bheight;
        REQUIRE(offset <= 4096);
    }
    REQUIRE(offset + g->bwidth * g->bheight <= 4096);
    unsigned n = g->txb_count[b->tx_depth]; REQUIRE(n <= MAX_TXB_COUNT);
""")
    after = manifest(NEW)
    a, b = {x[0]: x[1:] for x in before}, {x[0]: x[1:] for x in after}
    assert a.keys() == b.keys()
    changed = {name for name in a if a[name] != b[name]}
    assert changed == {"Source/Lib/Codec/" + n for n in ("pc_impl.h", "pb_trace.h", "pb_trace.c")}
    patch = ""
    for name in sorted(changed):
        patch += "".join(difflib.unified_diff(
            (OLD/name).read_text().splitlines(keepends=True), (NEW/name).read_text().splitlines(keepends=True),
            fromfile="a/"+name, tofile="b/"+name))
    OUT.mkdir()
    (OUT/"source-manifest.json").write_text(json.dumps(after, indent=2)+"\n")
    (OUT/"observer-only.patch").write_text(patch)
    assert manifest(OLD) == before and manifest(NEW) == after
    result = dict(status="prepared_not_built", script=ident(Path(__file__)), old_source=str(OLD),
                  new_source=str(NEW), base_manifest=ident(MANIFEST), manifest=ident(OUT/"source-manifest.json"),
                  patch=ident(OUT/"observer-only.patch"), changed_files=sorted(changed),
                  scope="Observer offset correction only; original policy runs remain immutable.")
    (OUT/"receipt.json").write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result))


if __name__ == "__main__":
    if not __debug__:
        raise RuntimeError("optimized Python prohibited")
    main()
