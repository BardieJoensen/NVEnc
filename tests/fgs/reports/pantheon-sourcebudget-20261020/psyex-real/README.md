# R15 frozen reproduction and evidence

See ../PSYEX_REAL.md and ../ROUND15_REAL_CONTRACT.md for conclusions and scope.
manifest.json binds each frozen file to its measured scratch source. Native traces,
media and full control tiles remain external and hash-bound; their receipts retain
original paths. The historical scripts intentionally retain original-prefix pins.
ARCHIVAL_NOTES.md explains why a relocation symlink alone cannot satisfy exact-path
execution checks. No archive has been made yet; later rounds still depend on these files.

Reproduce in the original scratch prefix with pinned R8 app/library, R11 observer,
R10 decoder, original fixture and recorded dependencies restored. encode.json contains
both literal encode commands; encoder-{off,on}.json and decoder-{off,on}.json contain
all neutral replay commands. *-execution*.json contain actual validation, admission,
scoring, stage and comparison invocations with script hashes and return codes. Use
fresh output directories for reruns; do not overwrite evidence. The first scoring
attempt failed before metrics on an identity-schema bug; the second is the valid run.
