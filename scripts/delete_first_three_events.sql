-- Remove the three oldest events by primary key (signups cascade in app schema).
-- Run in Neon SQL editor or: psql "$DATABASE_URL" -f scripts/delete_first_three_events.sql
WITH doomed AS (
  SELECT id FROM events ORDER BY id ASC LIMIT 3
)
DELETE FROM events e
USING doomed d
WHERE e.id = d.id;
