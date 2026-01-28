#!/usr/bin/env bash
screen_name=tiktok

set -eo pipefail


# Detect Docker, although variable should have been already set by Dockerfile
if [ -f /.dockerenv ] || grep -qa docker /proc/1/cgroup >/dev/null 2>&1;
then
  IN_DOCKER=1
fi

# If not in Docker and not already in screen → re-exec in screen
if [ -z "$IN_DOCKER" ] && [ -z "$STY" ]
then
    # we are not running in screen
    exec screen -dm -S ${screen_name} -L -Logfile ${screen_name}_$(date '+%d_%m_%Y_%H_%M_%S').log /bin/bash "$0";
    
else
    # we are running in screen or in Docker, provide commands to execute
    ./start.sh PROD streamers_config.json
fi


