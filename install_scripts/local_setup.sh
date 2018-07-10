#!/usr/bin/env bash

set -ev

POSTGRES_USER=${TRAVIS_POSTGRES_USER:-postgres}

psql -c "create extension if not exists postgis" -U $POSTGRES_USER
psql -c "update pg_database set encoding = 6, datcollate = 'en_US.UTF8', datctype = 'en_US.UTF8' where datname = 'template0';" -U $POSTGRES_USER
psql -c "update pg_database set encoding = 6, datcollate = 'en_US.UTF8', datctype = 'en_US.UTF8' where datname = 'template1';" -U $POSTGRES_USER
psql -c "drop user if exists betterbeauty;" -U $POSTGRES_USER
createdb betterbeauty -T template0 -E UTF8 --locale=en_US.UTF8  -U $POSTGRES_USER
psql -c "create user betterbeauty with password 'W8zSrpqUkFzReUqT';" -U $POSTGRES_USER
psql -c "alter user betterbeauty with superuser" -U $POSTGRES_USER
