# ACIMA adoption plan — <repository>

Owner: <name>            Sponsor: <name>            Start: <date>            Review: monthly

## 1. Context

- Mode: <greenfield | brownfield | adopting>
- Language profile: <dotnet | typescript | python | go | java>
- Declared level today: <L1 | L2 | L3 | none>
- Architecture family in use: <Clean | Hexagonal | DDD | modular monolith | microservices | mixed> — what ACIMA adds: <one sentence in the team's terms>
- Why now: <the incident, coupling or reorg that made this worth doing>
- What is explicitly out of scope: <e.g. persistence ownership this year>

## 2. Unit map (ADR-0001)

| Unit | Role | Paths | Owning team | Owner |
|---|---|---|---|---|
| <orders.contracts> | contracts | <src/Orders/Orders.Contracts> | <team> | <name> |
| <orders> | implementation | <src/Orders/Orders> | <team> | <name> |

Value types (`Money`, ids) live in the contracts project that publishes them. Do not add a
shared-kernel row unless you are recording a legacy exception with an owner and expiry.

Decision: <why these boundaries; what was considered and rejected>

## 3. Phases

| Phase | Outcome | Date | Owner | Evidence |
|---|---|---|---|---|
| Calibrate | preflight passes | <date> | <name> | preflight report |
| Baseline | findings measured and owned | <date> | <name> | baseline JSON + waivers |
| Gate | CI blocks new errors | <date> | <name> | required check link |
| First slice | <boundary change> merged | <date> | <name> | PR # |
| Ratchet | count non-increasing for a quarter | <date> | <name> | monthly one-pager |

## 4. First slice

- Boundary: <module A → module B>
- Change: <replace implementation import with contracts call / break cycle / freeze contract>
- Size estimate: <files, ~lines>
- Risk: <schema? deployment ordering? consumer count?>
- Rollback: <revert the PR; no data change>

## 5. Metrics

| Metric | Today | 90 days | Source |
|---|---|---|---|
| Unwaived errors | <n> | 0 | enforcer JSON |
| Total findings at level | <n> | -40% | enforcer JSON |
| Unowned waivers | <n> | 0 | waiver file |
| Lead time (median) | <n> | no worse | existing dashboard |

## 6. Risks and escalations

| Risk | Impact | Owner | Mitigation |
|---|---|---|---|
| <team disagrees on concept ownership> | boundary churn | <name> | decision by <date> |
| <migration blocks A001> | L3 delayed | <name> | start schema design in Q2 |

## 7. Review cadence

- Weekly: 30-minute office hours, count + blockers.
- Monthly: one-page update to <group>; waiver review.
- Quarterly: level decision (raise, hold, amend a rule).

## 8. Exit criteria

- [ ] gate required on the default branch
- [ ] zero unowned waivers
- [ ] one boundary change merged
- [ ] run artefact retained for the last verified commit
- [ ] team can run the gate without the architecture owner present
