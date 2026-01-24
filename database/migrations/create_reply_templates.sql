-- Migration: Create reply_templates table
-- Created: 2026-01-24
-- Purpose: Store reply templates for users

CREATE TABLE IF NOT EXISTS reply_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create index on user_id for faster queries
CREATE INDEX IF NOT EXISTS idx_reply_templates_user_id ON reply_templates(user_id);

-- Enable Row Level Security
ALTER TABLE reply_templates ENABLE ROW LEVEL SECURITY;

-- Create RLS policies
-- Users can only read their own templates
CREATE POLICY "Users can view own templates" ON reply_templates
    FOR SELECT
    USING (auth.uid()::text = user_id);

-- Users can only insert their own templates
CREATE POLICY "Users can insert own templates" ON reply_templates
    FOR INSERT
    WITH CHECK (auth.uid()::text = user_id);

-- Users can only delete their own templates
CREATE POLICY "Users can delete own templates" ON reply_templates
    FOR DELETE
    USING (auth.uid()::text = user_id);

-- Users can only update their own templates
CREATE POLICY "Users can update own templates" ON reply_templates
    FOR UPDATE
    USING (auth.uid()::text = user_id);
