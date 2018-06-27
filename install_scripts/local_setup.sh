#!/usr/bin/env bash
psql -c "update pg_database set encoding = 6, datcollate = 'en_US.UTF8', datctype = 'en_US.UTF8' where datname = 'template0';" -U postgres
psql -c "update pg_database set encoding = 6, datcollate = 'en_US.UTF8', datctype = 'en_US.UTF8' where datname = 'template1';" -U postgres
dropdb betterbeauty -U postgres || true
psql -c "drop user if exists betterbeauty;" -U postgres
createdb betterbeauty -T template0 -E UTF8 --locale=en_US.UTF8  -U postgres
psql -c "create user betterbeauty with password 'W8zSrpqUkFzReUqT';" -U postgres
psql -c "alter user betterbeauty with superuser" -U postgres