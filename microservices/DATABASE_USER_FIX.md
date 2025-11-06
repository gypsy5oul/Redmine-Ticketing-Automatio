# Database User Fix

## Problem

The error "FATAL: role 'devops_user' does not exist" occurs when the PostgreSQL database volume exists but the required user wasn't created during initialization.

This happens when:
- The database was initialized before with different credentials
- The user was manually deleted
- The database is being reused from a different setup

## Solution

### Option 1: Run the automated script (Recommended)

```bash
cd /home/user/Redmine-Ticketing-Automatio/microservices
./create-db-user.sh
```

Then restart the services:

```bash
docker-compose -f docker-compose.microservices.yml restart
```

### Option 2: Manual commands

If the script doesn't work, run these commands manually:

```bash
# Enter the postgres container
docker-compose -f docker-compose.microservices.yml exec postgres psql -U postgres

# Then run these SQL commands:
CREATE USER devops_user WITH PASSWORD 'devops_password_change_this';
GRANT ALL PRIVILEGES ON DATABASE devops_tickets TO devops_user;

\c devops_tickets

GRANT ALL ON SCHEMA public TO devops_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO devops_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO devops_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO devops_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO devops_user;

\q
```

### Option 3: Using docker exec (if docker-compose not available)

```bash
# Enter the container
docker exec -it devops-tickets-db psql -U postgres

# Then run the same SQL commands as Option 2
```

## Verification

After running the fix, verify the user exists:

```bash
# Check user exists
docker-compose -f docker-compose.microservices.yml exec postgres psql -U postgres -c "\du devops_user"

# Test connection with the new user
docker-compose -f docker-compose.microservices.yml exec postgres psql -U devops_user -d devops_tickets -c "SELECT current_user, current_database();"
```

## Check Service Logs

After restarting, the error should be gone:

```bash
# Check for errors
docker-compose -f docker-compose.microservices.yml logs postgres | grep -i fatal

# Check auth service can connect
docker-compose -f docker-compose.microservices.yml logs auth-service | tail -20
```

## Why This Happened

The PostgreSQL environment variables (`POSTGRES_USER`, `POSTGRES_PASSWORD`) only work during **initial database creation**. When the database already exists (from the old app), PostgreSQL skips initialization and doesn't create the user.

Since we're reusing the existing `postgres_data` volume, we need to manually create the user if it doesn't exist.
