#!/usr/bin/env bash
sudo -u postgres psql -c "update pg_database set encoding = 6, datcollate = 'en_US.UTF8', datctype = 'en_US.UTF8' where datname = 'template0';"
sudo -u postgres psql -c "update pg_database set encoding = 6, datcollate = 'en_US.UTF8', datctype = 'en_US.UTF8' where datname = 'template1';"
sudo -u postgres dropdb betterbeauty || true
echo "drop user if exists betterbeauty;" | sudo -u postgres psql
sudo -u postgres createdb betterbeauty -T template0 -E UTF8 --locale=en_US.UTF-8
echo "create user betterbeauty with password 'W8zSrpqUkFzReUqT';" | sudo -u postgres psql
echo "alter user betterbeauty with superuser" | sudo -u postgres psql
