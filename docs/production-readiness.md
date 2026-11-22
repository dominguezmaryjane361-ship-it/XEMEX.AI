# XEMEX.AI production readiness

This branch contains development changes only. It must not be treated as a production-ready release or merged automatically.

## What is implemented in this branch

- Supabase Auth accounts for parents/adult learners and self-managed student accounts for ages 13+.
- Parent-created learner profiles for ages 13–17.
- Under-13 account/profile creation is blocked until a verifiable parental-consent workflow is implemented and independently tested.
- Per-account memory and private student account storage.
- Owner-only Row Level Security policies for `user_memories`.
- Server-side student account storage using the Supabase service-role key.
- Dedicated student session signing secret; no fallback to the service-role key.
- Parent re-authentication before parent-only settings, profile management, PIN changes, progress observations, dashboards, data export, and account deletion.
- Parent controls to pause chat, practice, and hints.
- Student tutor and wellbeing-companion modes with age-aware system prompts.
- Deterministic keyword escalation for a small set of self-harm, abuse, and immediate-danger phrases.
- Password recovery entry points.
- Account data export and password-confirmed account deletion.
- Python compilation and unit-test workflow.

## Required Render environment variables

Set these in the Render service's Environment settings. Do not commit secrets to GitHub or place them in Gradio/browser code.

| Variable | Required | Purpose |
|---|---:|---|
| `GROQ_API_KEY` | Yes | Server-side model API key |
| `GROQ_MODEL` | Yes | Model identifier supported by the Groq account |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_KEY` | Yes | Supabase anon/publishable key for Auth and user-JWT requests; not the service-role key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Server-only access to student accounts and Supabase Auth Admin deletion |
| `XEMEX_STUDENT_SESSION_SECRET` | Yes | Dedicated random secret, at least 32 characters; never reuse the Supabase service-role key |
| `XEMEX_SHOW_ERRORS` | No | Keep `false` in production; set `true` only for private debugging |
| `ENABLE_HEARTBEAT` | No | Keep `false` until background tasks receive a separate security and privacy review |

Generate a dedicated student-session secret with a secure password manager or a cryptographically secure generator, for example:

```python
import secrets
print(secrets.token_urlsafe(48))
```

Never paste secret values into issues, chat, screenshots, or public commits. Rotate any credential that may have been exposed.

## Required Supabase setup

Run these SQL files in the Supabase SQL Editor, in this order:

1. `supabase/user_memories.sql`
2. `supabase/student_accounts.sql`

Then verify in Supabase:

- `user_memories` has RLS enabled and authenticated users can only select/insert/update the row where `auth.uid() = user_id`.
- `student_accounts` has RLS enabled, no anon/authenticated policies, and server-side service-role access only.
- `student_accounts.parent_user_id` references `auth.users(id)` with `ON DELETE CASCADE`.
- Auth email confirmation, password recovery, Site URL, and redirect URLs are configured for the actual production domain.
- No service-role key is present in the browser bundle, repository, logs, or Gradio component values.

## Child privacy and wellbeing launch blockers

**Do not enable accounts for children under 13 yet.** The current code blocks under-13 self-registration and parent-created profiles because no verifiable parental-consent provider or verified consent evidence flow is integrated. A parent checkbox or self-declared age is not sufficient.

The wellbeing mode is a supportive AI companion, not counseling or therapy. Keyword matching is not reliable crisis detection, can miss messages, and can produce false positives. The chat is not monitored live, and XEMEX cannot alert a parent, contact a trusted adult, or call emergency services. Do not advertise the product as a counselor, therapist, crisis line, or supervised service.

Before serving minors, complete all of the following:

- Choose and integrate a legally appropriate verifiable parental-consent method for under-13 users; store auditable consent evidence and provide parent withdrawal/deletion controls.
- Obtain specialist child-privacy and COPPA review, plus applicable state privacy and consumer-protection review.
- Commission independent application-security testing, including authentication, authorization, RLS, account enumeration, session theft, rate limits, and cross-account data isolation.
- Add robust content moderation and safety testing beyond keyword matching, with documented handling for self-harm, abuse, grooming, exploitation, bullying, and dangerous instructions.
- Establish a real human safeguarding/escalation process before implying that a person monitors or responds to safety disclosures.
- Test parent/student boundaries on shared devices and ensure parent-only actions cannot be invoked without fresh parent re-authentication.
- Publish reviewed privacy policy, terms, retention/deletion schedule, contact details, and clear AI limitations.
- Complete Google Play Families / target-audience / Data safety declarations as applicable.

## Release checklist

- [ ] All GitHub Actions checks pass on the final commit.
- [ ] Supabase migrations have been applied and RLS tested with separate parent/student accounts.
- [ ] Render environment variables are set and verified without exposing values.
- [ ] Render deploys from the intended production branch only after review.
- [ ] Registration, email confirmation, sign-in, password reset, sign-out, and account deletion tested end-to-end.
- [ ] Parent-created student login, self-managed 13+ account, PIN lockout, chat pause, practice pause, and hint pause tested.
- [ ] Two unrelated accounts cannot read or overwrite each other's memory or student records.
- [ ] Data export is checked for completeness and excludes password hashes, tokens, and secrets.
- [ ] Mobile, accessibility, keyboard, screen-reader, and low-bandwidth tests completed.
- [ ] Child privacy, safety, moderation, human escalation, and legal launch blockers resolved before minors are onboarded.

## Test locally

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
```

The GitHub Actions workflow runs the same compile and unit-test commands. Passing these tests does not prove live Supabase, Render, email, Groq, mobile, or child-safety behavior.
