# Independent student sign-in setup

This feature supports either a parent-created **username + password** or a parent-created **email + password** for each learner. The email is a sign-in alias stored by XEMEX; it is not a separate Supabase Auth identity and does not send email-verification or password-reset messages.

## 1. Create the student account table

In the Supabase project connected to XEMEX, open **SQL Editor**, create a new query, paste the contents of `supabase/student_accounts.sql`, and run it.

The table has Row Level Security enabled and deliberately has no `anon` or `authenticated` policies. Only the server-side service role accesses it. Student passwords are stored as salted PBKDF2 hashes, never plaintext.

## 2. Add server-only environment variables

In the XEMEX hosting service's environment settings, add:

- `SUPABASE_SERVICE_ROLE_KEY`: the Supabase service-role secret key. Keep it server-side; never put it in Gradio/browser code or share it in chat.
- `XEMEX_STUDENT_SESSION_SECRET`: a long, random secret used to sign student sessions (use at least 32 random bytes).

The existing `SUPABASE_URL`, `SUPABASE_KEY`, and `GROQ_API_KEY` settings are still required for their existing functions. Do not replace the publishable `SUPABASE_KEY` with the service-role key.

## 3. Parent and student flow

1. A parent signs in to XEMEX using the existing parent account.
2. In **Parent view**, the parent creates a learner profile.
3. In **Independent student sign-in**, the parent assigns a unique username, optional email alias, and password.
4. The learner signs out of the parent view and uses the student sign-in on the welcome screen. They can enter either their username or email alias with the same password.
5. The parent can reset that learner's password from Parent view.

Student chat history and learning progress are stored in the separate `student_accounts.memory_data` record. Parent safety settings are read from the linked parent learner profile and applied to student practice and hint activities. The parent dashboard can display student practice and hint activity.

## Security notes

- The service-role key is a high-privilege secret and must exist only in the server environment.
- Student sessions are signed, expire after eight hours, and are held in server-side Gradio state.
- Five failed password attempts lock the student login for 15 minutes. A parent password reset clears the lockout.
- Student accounts are linked to the parent account and learner profile. This is not a general public self-registration system.
- The email option is a login alias only. Email confirmation and email-based recovery are not implemented.
