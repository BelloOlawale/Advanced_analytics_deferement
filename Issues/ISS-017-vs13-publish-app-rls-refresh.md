---
id: ISS-017
title: VS13 - Publish app, row-level security, refresh schedule & distribution
type: vertical-slice
slice: VS13
status: backlog
priority: P1
depends_on: [ISS-016, ISS-011]
runtime: fabric
---
# ISS-017 — VS13: Publish app, RLS, refresh & distribution

## Why
A report nobody can reach, or that shows the wrong asset to the wrong person, is not delivered. This slice makes the output distributable, secure and always current.

## Goal / demo
- The report is published as an **app** in the client workspace.
- **Row-level security** restricts each user to their asset(s).
- **Refresh** runs after the daily build (DirectLake or scheduled).
- Users reach the app and see only their data.

## In scope
- Create and publish the Power BI app.
- Define and test RLS roles (by asset), with a positive and negative test per role.
- Configure refresh to follow the daily build.
- Distribution list, access groups, and a short usage guide.

## Out of scope
- Model and page build (ISS-015, ISS-016).
- Alert delivery mechanics (ISS-011).

## Acceptance criteria
- [ ] App published; intended users can open it.
- [ ] RLS verified: a user sees only their asset's rows.
- [ ] Refresh completes automatically after the daily build (no manual step).
- [ ] Access groups documented; onboarding steps written.

## Tasks
- [ ] Configure roles and test users.
- [ ] Publish the app and set audiences.
- [ ] Wire refresh to the build schedule.
- [ ] Write the access/usage guide.

## Data / dependencies
Report (ISS-016), alerting (ISS-011), workspace admin for access groups.

## Notes
RLS by asset keeps multi-asset deployments safe.
