-- Private per-user memory for XEMEX parent/adult accounts.
-- Run in Supabase SQL Editor before enabling account memory.
CREATE TABLE IF NOT EXISTS public.user_memories (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    memory_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.user_memories ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.user_memories FROM anon;
GRANT SELECT, INSERT, UPDATE ON TABLE public.user_memories TO authenticated;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'user_memories'
          AND policyname = 'Users can read their own XEMEX memory'
    ) THEN
        CREATE POLICY "Users can read their own XEMEX memory"
            ON public.user_memories FOR SELECT TO authenticated
            USING (auth.uid() = user_id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'user_memories'
          AND policyname = 'Users can create their own XEMEX memory'
    ) THEN
        CREATE POLICY "Users can create their own XEMEX memory"
            ON public.user_memories FOR INSERT TO authenticated
            WITH CHECK (auth.uid() = user_id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'user_memories'
          AND policyname = 'Users can update their own XEMEX memory'
    ) THEN
        CREATE POLICY "Users can update their own XEMEX memory"
            ON public.user_memories FOR UPDATE TO authenticated
            USING (auth.uid() = user_id)
            WITH CHECK (auth.uid() = user_id);
    END IF;
END
$$;

-- Student accounts are managed server-side using SUPABASE_SERVICE_ROLE_KEY.
-- Never expose that key to the browser or client-side Gradio code.
