# ClusterShell Governance

This document describes the governance model of the ClusterShell project.

ClusterShell is maintained by a small group of maintainers. The project aims to remain lightweight and responsive while ensuring continuity if an individual maintainer becomes unavailable.

## Roles

### Maintainers

Maintainers collectively form the project’s Technical Steering Committee (TSC).

**Role**

Maintainers are responsible for the technical direction and day-to-day operations of the project:

- Review, approve, and merge contributions
- Maintain project quality (tests/CI, coding standards, releases)
- Triage issues and manage roadmap/priorities
- Perform administrative operations on project infrastructure (repository settings, CI, packaging, etc.)
- Create and publish releases (including PyPI releases)

**Current roster (GitHub)**

- Stéphane Thiell (`@thiell`) — Lead maintainer
- Aurélien Degrémont (`@degremont`) — Maintainer
- Dominique Martinet (`@martinetd`) — Maintainer

> Note: Machine/service accounts (eg. CI bots) may have repository access but are not part of governance.

**Lead maintainer**

The Lead maintainer coordinates project operations and is responsible for ensuring timely decisions, including final decisions when consensus cannot be reached.

Currently: `@thiell`.

### Contributors

Contributors are anyone who reports issues, submits pull requests, improves documentation, or otherwise participates in the project.

Contributors are expected to follow the project’s Code of Conduct and contribution guidelines.

## Decision-making

ClusterShell uses a consensus-seeking, maintainer-led model:

- Most decisions are made through discussion on GitHub issues and pull requests.
- For routine changes, maintainers aim for **lazy consensus**: if there are no objections from maintainers after review, the change may be merged.
- For significant changes (eg. architecture, backward-incompatible behavior, security-sensitive changes), maintainers should seek explicit agreement from at least one other maintainer before merging.

If maintainers cannot reach consensus in a reasonable timeframe, the Lead maintainer makes the final decision.

## Contributions and merging

- Changes should be proposed via pull requests.
- Maintainers are expected to ensure CI is green (when available) and that changes meet project quality expectations before merging.
- Non-trivial changes require at least one approval from another maintainer before merge.

## Maintainer continuity / bus factor

To reduce single-maintainer risk:

- The project maintains multiple maintainers with write access.
- If the Lead maintainer becomes unavailable for an extended period, the remaining maintainers may designate a new Lead maintainer by agreement.
- If a maintainer becomes unresponsive or wishes to step down, repository access may be adjusted by the remaining maintainers.

## Adding or removing maintainers

- New maintainers may be nominated by any current maintainer.
- Selection is based on sustained, high-quality contributions and alignment with project practices.
- Adding a maintainer requires agreement of the existing maintainers.

Maintainers may step down at any time.

## Releases and release notes

- Release planning (scope, timing, and next version number) is discussed by maintainers (typically in the ClusterShell maintainer Slack channel).
- The Lead maintainer coordinates releases; maintainers aim for consensus on release scope and versioning. In case of disagreement, the Lead maintainer makes the final call.
- Releases are tagged in Git and published to PyPI by maintainers with PyPI access.
- For each release, maintainers publish public release notes in the documentation:
  https://clustershell.readthedocs.io/en/latest/release.html
- When applicable, GitHub milestones/issues are used to track release work, and release notes may reference the relevant milestone.

## Communication channels

- **GitHub (issues and pull requests)** is the primary public forum for user support, bug reports, and technical discussion.
- The project also uses an **invite-only ClusterShell Slack** for maintainer and supporter coordination.
  - Some discussions are maintainer-only (private).
  - Where appropriate, maintainers will summarize decisions that affect users or contributors (eg. release scope, policy changes, deprecations) in public on GitHub and/or in the published release notes.
