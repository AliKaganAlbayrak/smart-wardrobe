-- Run once in the Supabase SQL Editor BEFORE deploying multi-user code.
-- Repeatable, non-destructive. Does not claim legacy records or remove policies
-- belonging to other applications. Backend table-owner/service-role access stays.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '10s';

ALTER TABLE public.clothes ADD COLUMN IF NOT EXISTS owner_id UUID;
CREATE INDEX IF NOT EXISTS ix_clothes_owner_id ON public.clothes (owner_id);
ALTER TABLE public.clothes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS smart_wardrobe_owner_guard_v1 ON public.clothes;
CREATE POLICY smart_wardrobe_owner_guard_v1 ON public.clothes
  AS RESTRICTIVE FOR ALL TO anon, authenticated
  USING ((SELECT auth.uid()) = owner_id)
  WITH CHECK ((SELECT auth.uid()) = owner_id);

-- A public bucket bypasses read policies. Keep existing objects, change privacy.
UPDATE storage.buckets SET public = FALSE WHERE id = 'clothing-images';

-- Restrictive policy ANDs with any pre-existing permissive policy. Unrelated
-- buckets are unaffected. Without a permissive policy, direct client access
-- remains denied; this application uses backend-only Storage requests.
DROP POLICY IF EXISTS smart_wardrobe_storage_guard_v1 ON storage.objects;
CREATE POLICY smart_wardrobe_storage_guard_v1 ON storage.objects
  AS RESTRICTIVE FOR ALL TO anon, authenticated
  USING (
    bucket_id <> 'clothing-images' OR (
      (SELECT auth.uid()) IS NOT NULL AND
      (storage.foldername(name))[1] = (SELECT auth.uid())::text
    )
  )
  WITH CHECK (
    bucket_id <> 'clothing-images' OR (
      (SELECT auth.uid()) IS NOT NULL AND
      (storage.foldername(name))[1] = (SELECT auth.uid())::text
    )
  );
COMMIT;
