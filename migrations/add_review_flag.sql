-- Add review_flag column to sessions table (for existing databases)
-- New databases get this column automatically via create_all on startup.
ALTER TABLE sessions ADD COLUMN review_flag VARCHAR(30);
