# Cricket Broadcast System 1.11.0-rc.2

Changes since 1.11.0-rc.1:

- Added **Universal player** to new and existing career records in Statistics.
  Keep one player ID and existing totals while using that person in several
  fantasy teams.
- Added a universal-player picker and saved-record links to team rosters.
  Existing roster rows can be linked without duplicating a player or replacing
  their role, captain setting, portrait or manual graphic values.
- Completed scorecards retain player links, and results review selects those
  records automatically. Submitted performances from different teams accumulate
  in one read-only player profile.
- A universal player can represent both sides in a fantasy match. Each innings
  contributes to the same career record; the match counts once. Corrections,
  withdrawal and duplicate protection continue to work with shared identities.
- Added public Universal badges, combined team membership and team labels for
  individual innings. Ordinary players and unrelated matching names remain
  protected from accidental merging.

The database upgrade adds the new option while preserving player IDs, existing
results and totals. Current matches, recordings and certificates remain in the
separate saved-data folder. No existing duplicate player records are silently
merged. See STATISTICS_GUIDE.md for the setup steps and correction workflow.

Validation includes legacy-database migration, multiple fantasy teams, head-to-head
shared players, corrections/withdrawal, roster validation, duplicate submissions
and browser workflows in dark/light themes at desktop, tablet and phone widths.
This is an unsigned Windows prerelease with bundled Python.
