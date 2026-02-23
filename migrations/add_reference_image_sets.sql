-- Add reference_image_sets table and related columns (for existing databases)
-- New databases get these automatically via create_all on startup.

-- reference_image_sets table is created by create_all

-- Add set_id column to reference_images
ALTER TABLE reference_images ADD COLUMN set_id VARCHAR(26) REFERENCES reference_image_sets(id) ON DELETE CASCADE;

-- Add active_ref_set_id column to room_templates
ALTER TABLE room_templates ADD COLUMN active_ref_set_id VARCHAR(26) REFERENCES reference_image_sets(id) ON DELETE SET NULL;

-- Add reference_set_id column to comparisons
ALTER TABLE comparisons ADD COLUMN reference_set_id VARCHAR(26) REFERENCES reference_image_sets(id) ON DELETE SET NULL;
