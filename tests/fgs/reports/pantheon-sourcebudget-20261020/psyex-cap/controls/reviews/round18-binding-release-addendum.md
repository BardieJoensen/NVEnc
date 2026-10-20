# R18 header-binding release addendum

Focused delta from reviewed v1:

- final `bind_headers.py` SHA-256 `2fcce467cbd6ef3a09f5adb076db47289472ed93441cabc3e89bcc08e05e235d`
- preserved reviewed v1 SHA-256 `20d998ab1f432001ecd839ab5abe1c5bf2cc3701da688f93a4d8764504a5df34`

The only change replaces the removable `assert __debug__` with an explicit `if not __debug__: raise RuntimeError("optimized Python prohibited")` before `main()`. The prior blocker is resolved and no mapping, parser, provenance or evidence logic changed.

**Released for one fresh, outer-bound R18 cap-stream binding execution.** Computed target event/ordinal/order-hint/slot/OBU values remain outcomes and must be checked before any private observer is reused.
