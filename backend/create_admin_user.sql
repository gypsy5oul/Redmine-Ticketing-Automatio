-- Create initial admin user for the portal
-- Password: admin123 (hashed with bcrypt)
-- IMPORTANT: Change password after first login!

INSERT INTO users (
    username,
    email,
    hashed_password,
    full_name,
    role,
    active,
    two_factor_enabled,
    failed_login_attempts,
    created_at
) VALUES (
    'admin',
    'admin@devops.local',
    -- Password: admin123 (bcrypt hash)
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqJQvJ4l6e',
    'System Administrator',
    'SUPER_ADMIN',
    true,
    false,
    0,
    NOW()
)
ON CONFLICT (username) DO NOTHING;

-- Verify the user was created
SELECT 
    id,
    username, 
    email, 
    full_name, 
    role, 
    active,
    created_at 
FROM users 
WHERE username = 'admin';
