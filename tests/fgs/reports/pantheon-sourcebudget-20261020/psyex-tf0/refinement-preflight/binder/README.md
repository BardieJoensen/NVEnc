# Independent R16 refinement header binder

`bind_refine_headers.py` is the accepted R16 binder `cc50a6c5...` with only
these admission changes:

- pin midpoint-refinement runner `5804a1a5...` and addendum `9ea9b3bd...`;
- validate initial low/high endpoint arguments or the later predecessor
  argument in the outer execution receipt;
- require the original R16 contract and both canonical old endpoint receipts
  to occur in the runner-validated lineage; and
- label the output as midpoint-refinement evidence.

IVF/OBU framing, header parsing, reference-slot lifecycle, target display
selection, rate admission and output schema are unchanged. `--help` and Python
bytecode compilation passed. The binder has not been run because no matched
refinement encode exists yet.

Script SHA-256:
`5d30f960504b12d840d9cd916140dac5b24ae2053852c88a5a66b87ae1b347dc`.
