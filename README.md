# Introduction
BetterBeauty source code monorepo. This repo contains all source code for all our applications.

# Directory Structure

The repository has the following structure:
```
/mobile  - mobile Ionic application.
/webapp  - application backend API and admin.
/website - betterbeauty.com public web site.
```

# Contributing

Below are general guidelines that you need to follow
when contributing to this repo. See also additional guideance
on specific apps in `/mobile/README.md` and
`/webapp/README.md` files.

## Branching Model

We practice Continuous Deployment with 2 mainline branches:
`develop` and `master`.
Commiting to `develop` branch will trigger automatic build
and deployment of staging enviroment. Commiting to `master`
branch will trigger automatic build and deployment of
production enviroment.

We use feature branches temporarily during development
of features. Feature branches use
`feature/<your-slack-name>/<feature-name>` convention.
Feature branches are short-lived and exist only while
the feature is being developed or is under code review.
Do not keep long-lasting feature branches, otherwise you
risk facing merge conflicts which are never fun.

If you work on a large feature that can take more than a few
days to develop and requires multiple commits it is best
to commit to `develop` as you make progress but keep you
feature disabled using feature flags.

## Pull Requests and Code Reviews

Every change must be peer reviewed before it is merged to mainline branches. Push your feature branch to origin then go to VSTS
and create a pull request from that branch. If your change is
about UI then include screenshots showing what you did.

Once the pull request is created VSTS will automatially trigger
a build. Wait until the build succeeds and add appropriate
reviewers. Now wait for reviewers to comment.

After receiving comments fix the issues, work with the reviewer
to refine your work. If you need to make changes you can make additional commits on your feature branch or you can amend the
original commit. Push your changes to origin and reply to comments
in VSTS.

Once you and the reviewer are satisfied merge you pull request
using stashing. Use "Squash changes when merging" option in VSTS.
Delete your feature branch after closing the pull request.

## Automated Tests

All non-trivial functionality must be covered by automated tests.
Both web backend and mobile frontend have automated test suites.
Add your tests for any new feature you create or for any bug you fix.