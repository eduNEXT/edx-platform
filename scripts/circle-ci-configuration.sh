#!/usr/bin/env bash
###############################################################################
#
#   circle-ci-configuration.sh
#
###############################################################################

# From the sh(1) man page of FreeBSD:
# Exit immediately if any untested command fails. in non-interactive
# mode.  The exit status of a command is considered to be explicitly
# tested if the command is part of the list used to control an if,
# elif, while, or until; if the command is the left hand operand of
# an “&&” or “||” operator; or if the command is a pipeline preceded
# by the ! operator.  If a shell function is executed and its exit
# status is explicitly tested, all commands of the function are con‐
# sidered to be tested as well.
set -e

# Return status is that of the last command to fail in a
# piped command, or a zero if they all succeed.
set -o pipefail

EXIT=0

sleep $[ ( $RANDOM % 5 )  + 1 ]s

# Manually installing the mongo-3.6
apt-get update
apt-get install wget -y
wget -qO - https://www.mongodb.org/static/pgp/server-3.6.asc | sudo apt-key add -
echo "deb http://repo.mongodb.org/apt/ubuntu xenial/mongodb-org/3.6 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-3.6.list

sudo apt-get update

cat requirements/system/ubuntu/apt-packages.txt | DEBIAN_FRONTEND=noninteractive xargs apt-get -yq install

sudo add-apt-repository 'deb http://security.ubuntu.com/ubuntu bionic-security main'
curl -fsSL https://www.mongodb.org/static/pgp/server-3.6.asc | sudo apt-key add -
echo "deb [ arch=amd64,arm64 ] https://repo.mongodb.org/apt/ubuntu bionic/mongodb-org/3.6 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-3.6.list
apt update
apt-get install -y mongodb-org=3.6.20 mongodb-org-server=3.6.20 mongodb-org-shell=3.6.20 mongodb-org-mongos=3.6.20 mongodb-org-tools=3.6.20

#systemctl start mongod.service


mkdir -p downloads

DEBIAN_FRONTEND=noninteractive apt-get -yq install xvfb libasound2 libstartup-notification0

curl -fsSL https://deb.nodesource.com/gpgkey/nodesource.gpg.key | sudo apt-key add -
sudo add-apt-repository "deb https://deb.nodesource.com/node_12.x focal main"
sudo apt install nodejs

sudo apt install firefox
firefox --version

# To solve installation problems
apt-get install libsqlite3-dev -y
