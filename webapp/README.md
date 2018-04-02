# Prerequisites

- Python 3.6
- PostgreSQL >= 9.6


# Local setup and installation

- add following line to your `/etc/hosts` file:

`127.0.0.1 betterbeauty.local`
- go to `/webapp` folder and run `make setup-db`. It will set up local postgres db and 
will add default user. 

Note 1: admin priviliges will be required, since command uses `sudo`.
Alternatively, you may execute `install_scripts/local_setup.sh`.

Note 2: TODO: add note about different UTF-8 locales for OSX / Ubuntu users

- run `make run`. This command will create virtual environment, will set up Python modules
and will start development server at `http://betterbeauty.local:8000`


# Overriding default django settings

In `core/settings` there’s `local.py.def` file. If renamed to `local.py`, it will be
excluded from git tracking (it is is .gitignore` and will allow to override default
django settings. It’s useful to set some api keys for local testing,
or override some default settings.

# Other commands

- `make clean` - clean up cached python files
- `COMMAND=your_command make manage` - passes `your_command` to `manage.py`
- `make test` - run tests