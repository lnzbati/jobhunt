# Apply notes: what you've learned about specific careers sites

Copy to `profile/apply-notes.md` (gitignored). `/apply` reads it at the start of every run and
adds to it when it learns something about a site. Keep it to notes about **the site**, not
your personal answers (those belong in `profile.yaml`).

Useful things to record per site: how sign-in works, redirects to wait out, exact button
labels, fields the site pre-fills from earlier applications, upload input selectors, date
formats, and questions that repeat across steps.

## example-portal.com

- Learned 2026-01-15:
  - **Sign-in:** email → Continue → one-time code by email → Continue. After the code it
    briefly redirects through `/session/handoff`. Wait for the form to show.
  - **Buttons:** the first step says "Save & continue". The others say "Next".
  - **Pre-filled:** the CV and the "how did you hear" answer come from the last application.
    Always replace the CV and re-check that answer.
  - **Upload:** the CV input is `input[type=file]#resume-upload`.
  - **Dates:** start date uses `DD/MM/YYYY`.
