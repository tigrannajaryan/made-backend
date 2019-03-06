FROM ubuntu:16.04

# install pre-requisits layer
RUN apt-get update && apt-get -y install wget ca-certificates lsb-core
RUN wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -
RUN sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt/ `lsb_release -cs`-pgdg main" >> /etc/apt/sources.list.d/pgdg.list'

# install main layer of dependencies
RUN apt-get update && \
  apt-get install -y software-properties-common && \
  add-apt-repository -y ppa:jonathonf/python-3.6 && \
  apt-get update && \
  apt-get -y install libssl-dev libxml2-dev build-essential python3.6 python3.6-dev python3-dev python3.6-venv python3-pip postgresql-10 postgresql-client-10 postgresql-10-postgis-2.4

# fix postgres local authentication
RUN sed -i 's/local\s*all\s*postgres\s*peer/local all postgres trust/g' /etc/postgresql/10/main/pg_hba.conf

# link python executables
RUN ln -f /usr/bin/python3.6 /usr/bin/python
RUN ln -f /usr/bin/pip3 /usr/bin/pip

# set up source files
RUN mkdir /madebeauty
WORKDIR /madebeauty
COPY betterbeauty/ /madebeauty/betterbeauty/
COPY install_scripts/ /madebeauty/install_scripts/
COPY push_certificates/ /madebeauty/push_certificates/
COPY Makefile /madebeauty