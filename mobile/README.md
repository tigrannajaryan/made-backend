# Prerequisites

- node v8.11.1 or newer LTS
- npm 5.6.0 or newer

# Local setup and installation

- run `npm install` to install node modules.
- run `npm run ionic:serve`. This command will build the app, start a
local dev server for dev/testing and open the app in your default browser.

To build only run `npm run build`.

# Android App

## Prerequisites

- Following instructions for Android Devices here: https://ionicframework.com/docs/intro/deploying/

- set ANDROID_HOME env variable to the directory where you installed Android SDK
(this is usually "$HOME/Android/Sdk" on Linux).

- Go to `$ANDROID_HOME/tools/bin` directory, run `./sdkmanager --licenses` and accept all licenses.

- Install Gradle (for Ubuntu do `apt install gradle`)

## Building and running

To build and run on Android emulator or connected Android device
use command `ionic cordova run android --device`
