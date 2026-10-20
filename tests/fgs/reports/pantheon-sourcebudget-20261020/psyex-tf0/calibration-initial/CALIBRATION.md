# R16 measured-rate calibration

The committed contract fixes the scored 96:336 packet interval at
9.579757176–9.6765224 Mbps (99–100% of source). Only the bitrate request may
change between these attempts. Each uses fresh two-pass statistics and the
same frozen runner `2c14604755be12ae1f8fe996cc93ea9486963f629e44bc3a1a7d21d40076469b`.
All actual launches use outer wrapper `93c0740995afa0b6c1bf91c5c5bacbe620558e9a327493edf71406e8a68f4858`.

Attempt 1, request 10313 kbps, completed:

- Scored Matroska video packets: 9.880460800000002 Mbps.
- Full 336-frame Matroska video packets: 10.254150857142855 Mbps.
- Pass 1: 64.6434767699102 s; pass 2: 311.17488457704894 s.
- Total encoder time: 375.81836134695914 s. Outer wall time includes validation.
- Inner receipt: `90b6df06c93ae6e048ee37f0584f17b658f38c674af81fb03ccc785c34271a33`.
- Outer receipt: `5b01f1c9383921ffd7cd65860c9ea04bfba09ade794d49f09a756930df209b3b`.
- Above the source ceiling; ineligible for the decisive quality comparison.
  No quality assessment or playback claim was made.

Attempt 2 was selected by the unchanged rule:
`round(10313 * (0.997 * 9.6765224) / 9.880460800000002) = 10070`.
It is a bitrate calibration, not an alternative quality configuration.
Its fresh run directory is `worker/psyex-r16-tf0-budget/runs/e05-1440/r16-tf0-tbr10070`.

Attempt 2 completed above the ceiling:

- Scored rate 9.70136 Mbps; full336 rate 10.023637142857144 Mbps.
- Passes 64.60061116295401 and 308.43375988898333 s; total 373.03437105193734 s.
- Inner receipt `690beb605f882ddb9748f4e23f4aabc604cca1027f019b5ad09004b9b31b442a`.
- Outer receipt `3b1b8f47b47a2124470375a251ecabc4bd3ee1a332038cb7a37c14292cb650ae`.
- Above-source rate by 0.2566789904%; no decisive quality assessment.

The unchanged formula selects attempt 3:
`round(10070 * (0.997 * 9.6765224) / 9.70136) = 10014`.
Fresh statistics and all ancestor receipt bindings are retained.

Full-episode rate, speed and playback qualification remain separate requirements.
The scored-window budget must not be presented as full-episode qualification.
