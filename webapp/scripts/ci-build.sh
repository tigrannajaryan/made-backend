#!/usr/bin/env bash

# This script is used in CI system to perform the full build and test

echo "***************************** Setting up environment *****************************"
cd webapp
make setup-vsts

echo "***************************** Setting up DB ***************************** "
make setup-db

echo "***************************** Building *****************************"
make

echo "***************************** Starting test *****************************"
make test

echo "***************************** Copy requirements *****************************"
cd betterbeauty
echo -e '#' auto-generated by VSTS build process'\n'-r requirements/$(BuildDeployLevel).txt > requirements.txt