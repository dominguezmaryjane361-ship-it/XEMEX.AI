-- Private per-user memory for XEMEX parent/adult accounts.
-- Run in Supabase SQL Editor before enabling account memory.
CREATE TABLE IF NOT EXISTS public.user_memories (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    memory_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.user_memories
    ADD COLUMN IF NOT EXISTS memory_data JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE public.user_memories
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

DO $
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'public.user_memories'::regclass
          AND confrelid = 'auth.users'::regclass
          AND contype = 'f'
    ) THEN
        ALTER TABLE public.user_memories
            ADD CONSTRAINT user_memories_auth_user_fk
            FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE;
    END IF;
END
$;

CREATE UNIQUE INDEX IF NOT EXISTS user_memories_user_id_unique
    ON public.user_memories (user_id);

ALTER TABLE public.user_memories ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.user_memories FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON TABLE public.user_memories TO authenticated;
GRANT ALL ON TABLE public.user_memories TO service_role;

-- Remove pre-existing policies first: permissive RLS policies are ORed together.
DO $
DECLARE policy_row RECORD;
BEGIN
    FOR policy_row IN
        SELECT policyname FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'user_memories'
    LOOP
        EXECUTE format('DROP POLICY %I ON public.user_memories', policy_row.policyname);
    END LOOP;
END
$;

CREATE POLICY "Users can read their own XEMEX memory"
    ON public.user_memories FOR SELECT TO authenticated
    USING (auth.uid() = user_id);
CREATE POLICY "Users can create their own XEMEX memory"
    ON public.user_memories FOR INSERT TO authenticated
    WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can update their own XEMEX memory"
    ON public.user_memories FOR UPDATE TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- Student accounts are managed server-side using SUPABASE_SERVICE_ROLE_KEY.
-- Never expose that key to the browser or client-side Gradio code.
