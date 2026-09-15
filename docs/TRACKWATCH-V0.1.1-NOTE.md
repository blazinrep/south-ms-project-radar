# TrackWatch Contractor Adapter V0.1.1

This patch corrects the first source-health rule.

Project Radar's Mississippi procurement monitor performs lightweight discovery
against candidate detail IDs. Raw HTTP/network failures from that discovery are
useful telemetry, but they are **not automatically a reason to interrupt the
contractor**.

V0.1.1 separates:

- **raw fetch errors** — recorded in proof metrics / telemetry
- **source-health problems** — human alert only when a known record becomes
  `stale_unverified`, or when the procurement monitor explicitly reports itself
  unhealthy

This preserves the TrackWatch principle: **filter noise before asking for human
attention.**
