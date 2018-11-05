#!/usr/bin/env bash
set -evx

CERT_PATH="push_certificates"

# This script prepares .zip bundles to be deployed to Elastic Beanstalk.
# It prepares 2 bundles: bundles/staging.zip and bundles/production.zip
# These are the zip archives consisting of files from git ls-files command
# (which is the default behavior of travis's elasticbeanstalk deploy provider),
# and appropriate push notifications certificates are injected into each of
# the bundles.

# 1. Create staging and production bundles *without* decripted certificates.
# We're going to use current git local copy file list - since this is
# the default behavior of travis's elasticbeanstalk provider, which
# uses `git ls-files` in the default mode of operation. We will exclude
# any encrypted push certificates at this time

mkdir $TRAVIS_BUILD_DIR/$BUNDLE_PATH
zip $TRAVIS_BUILD_DIR/$BUNDLE_PATH/$STAGING_BUNDLE_NAME `git ls-files` --exclude $CERT_PATH/*.pem.enc
# at this point staging and production bundles must be equal
cp $TRAVIS_BUILD_DIR/$BUNDLE_PATH/$STAGING_BUNDLE_NAME $TRAVIS_BUILD_DIR/$BUNDLE_PATH/$PRODUCTION_BUNDLE_NAME

# 2. Decrypt certificates

# there are 4 server certificates to decrypt; local certificates are store unencrypted
openssl aes-256-cbc -d -a -K $encrypted_69fcb918905c_key -iv $encrypted_69fcb918905c_iv -in $CERT_PATH/server-client-staging.pem.enc -out $CERT_PATH/server-client-staging.pem
openssl aes-256-cbc -d -a -K $encrypted_69fcb918905c_key -iv $encrypted_69fcb918905c_iv -in $CERT_PATH/server-stylist-staging.pem.enc -out $CERT_PATH/server-stylist-staging.pem
openssl aes-256-cbc -d -a -K $encrypted_69fcb918905c_key -iv $encrypted_69fcb918905c_iv -in $CERT_PATH/server-client-production.pem.enc -out $CERT_PATH/server-client-production.pem
openssl aes-256-cbc -d -a -K $encrypted_69fcb918905c_key -iv $encrypted_69fcb918905c_iv -in $CERT_PATH/server-stylist-production.pem.enc -out $CERT_PATH/server-stylist-production.pem

# add previously decrypted staging keys to the staging archive
zip $TRAVIS_BUILD_DIR/$BUNDLE_PATH/$STAGING_BUNDLE_NAME $CERT_PATH/server-*-staging.pem
# add production keys to the production archive
zip $TRAVIS_BUILD_DIR/$BUNDLE_PATH/$PRODUCTION_BUNDLE_NAME $CERT_PATH/server-*-production.pem

# 3. Cleanup certificates
rm -rf $CERT_PATH/server*.pem