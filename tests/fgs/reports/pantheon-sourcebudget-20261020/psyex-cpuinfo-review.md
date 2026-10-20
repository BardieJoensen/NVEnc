# Round 8 nested cpuinfo provenance review

The root 1,217-file manifest did not include the ignored FetchContent checkout
at `source/third_party/cpuinfo`; therefore it must not be described as all source
compiled into the private build.

The supplemental audit is adequate for the already finished build:

- audit SHA: `697dd77268d11f1f8a1a5003f6f6e05e1206d3686904fa3b1f05e5b499a43190`
- 570-file manifest SHA:
  `2374575a0aba9b941152770a2374ec048eb540868366bbbb46df846896a4a63f`
- exact nested HEAD: `e649baaa95efeb61517c06cc783287d4942ffe0e`
- remote: `https://github.com/1480c1/cpuinfo.git`
- clean nested status including ignored/untracked paths
- CMake recipe pins the same commit and build.ninja identifies that checkout as
  the source of cpuinfo objects linked into the private SVT library.

I independently checked that the manifest exactly matches the ordered 570
tracked paths and every live `(size, SHA-256)` tuple. The result cannot recreate
a nonexistent pre-build nested-tree snapshot, but fixed final app/library hashes,
the pinned fetch recipe, clean exact checkout, and actual build graph make a
repeat build unnecessary for this experiment. The runner now revalidates every
nested manifest entry and binds both supplemental files before and after encode.

Required reporting scope: “root-tracked 1,217-file manifest plus post-build
570-file pinned cpuinfo supplement.” Do not call the root manifest complete.
