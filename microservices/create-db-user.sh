#!/bin/bash

# Script to create devops_user in existing PostgreSQL database
# This fixes the "role 'devops_user' does not exist" error

echo "============================================"
echo "Creating devops_user in PostgreSQL database"
echo "============================================"
echo ""

# Connect to postgres container and create user
docker-compose -f docker-compose.microservices.yml exec -T postgres psql -U postgres <<-EOSQL
    -- Create user if not exists
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_user WHERE usename = 'devops_user') THEN
            CREATE USER devops_user WITH PASSWORD 'devops_password_change_this';
            RAISE NOTICE 'User devops_user created successfully';
        ELSE
            RAISE NOTICE 'User devops_user already exists';
        END IF;
    END
    \$\$;

    -- Grant all privileges on database
    GRANT ALL PRIVILEGES ON DATABASE devops_tickets TO devops_user;

    -- Connect to devops_tickets database and grant schema permissions
    \c devops_tickets

    -- Grant all privileges on schema
    GRANT ALL ON SCHEMA public TO devops_user;

    -- Grant privileges on all existing tables
    GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO devops_user;

    -- Grant privileges on all existing sequences
    GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO devops_user;

    -- Grant default privileges for future tables
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO devops_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO devops_user;

    -- Make devops_user the owner of existing objects
    -- REASSIGN OWNED BY postgres TO devops_user;

    -- List users to verify
    \du devops_user
EOSQL

echo ""
echo "============================================"
echo "User creation complete!"
echo "============================================"
echo ""
echo "Now restart the services:"
echo "  cd /home/user/Redmine-Ticketing-Automatio/microservices"
echo "  docker-compose -f docker-compose.microservices.yml restart"
echo ""
