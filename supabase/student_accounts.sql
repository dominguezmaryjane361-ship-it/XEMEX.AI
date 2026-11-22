-- Run in Supabase SQL Editor once before enabling independent student accounts.
-- The service-role key is used only by the Python server; never place it in Gradio/browser code.

CREATE TABLE IF NOT EXISTS public.student_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    learner_id TEXT NOT NULL,
    username TEXT NOT NULL,
    email TEXT,
    password_salt TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    password_iterations INTEGER NOT NULL DEFAULT 310000,
    memory_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT student_accounts_username_format
        CHECK (username = lower(username) AND length(username) BETWEEN 3 AND 24),
    CONSTRAINT student_accounts_password_iterations
        CHECK (password_iterations BETWEEN 100000 AND 500000)
);

CREATE UNIQUE INDEX IF NOT EXISTS student_accounts_username_unique
    ON public.student_accounts (username);
CREATE UNIQUE INDEX IF NOT EXISTS student_accounts_email_unique
    ON public.student_accounts (lower(email))
    WHERE email IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS student_accounts_parent_learner_unique
    ON public.student_accounts (parent_user_id, learner_id);

ALTER TABLE public.student_accounts ENABLE ROW LEVEL SECURITY;

-- No anon/authenticated policies are intentionally created.
-- The backend uses SUPABASE_SERVICE_ROLE_KEY, which bypasses RLS.
REVOKE ALL ON TABLE public.student_accounts FROM anon, authenticated;
GRANT ALL ON TABLE public.student_accounts TO service_role;
