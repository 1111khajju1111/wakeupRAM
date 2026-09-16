# Wake Up Ram — Vision UI Update

This build updates the existing Phase-13 foundation toward the requested personal-operating-system experience.

## Changed
- Added a reusable authenticated `AppShell` with sticky header, theme control, identity affordance, and mobile bottom navigation.
- Reworked Home into a command-centre dashboard: live time, personalized greeting, today mission, habit progress, active goals, countdown, RAM Core call CTA, and module index.
- Preserved all existing domain APIs and routes; no demo data or hardcoded user tasks/countdowns were introduced.
- Added responsive mobile/tablet/desktop styling with monochrome technical visual language, dot-grid motif, thin borders, large numerals, restrained motion, and dense information hierarchy.
- Added English and Telugu strings for the new dashboard copy.

## Important
- Backend/security/domain features from the source project were preserved rather than replaced.
- `npm run build` could not be executed in this environment because dependencies are not installed locally and package installation timed out. Run `npm install` and then `npm run build` on the development machine.
