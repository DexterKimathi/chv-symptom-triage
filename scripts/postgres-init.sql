-- Run once by the postgres image when its data volume is first created.
-- The tests get their own database, so running them never touches development data.
CREATE DATABASE chv_test OWNER chv;
