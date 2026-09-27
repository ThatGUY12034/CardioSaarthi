-- A third T-wave error.
--
-- The taxonomy had two: the student missed an inversion, or called upright T
-- waves inverted. Now that the step is actually marked, a third mismatch turns
-- up that is neither -- calling a flat T wave upright, or a biphasic one flat.
-- Mapping those onto "called it inverted" would put the wrong lesson in front of
-- the student and the wrong row in the faculty analytics.

INSERT INTO error_labels (code, step, description) VALUES
    ('T_MORPHOLOGY_MISREAD', 8, 'T wave direction read as the wrong one of upright, flat or biphasic');
