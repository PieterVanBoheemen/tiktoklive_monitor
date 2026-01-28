#!/bin/bash
screen_name=tiktok

if [ -z "$STY" ]
then
    # we are not running in screen
    exec screen -dm -S ${screen_name} -L -Logfile ${screen_name}_$(date '+%d_%m_%Y_%H_%M_%S').log /bin/bash "$0";
    
else
    # we are running in screen, provide commands to execute

    ./start.sh PROD streamers_config.json

fi


