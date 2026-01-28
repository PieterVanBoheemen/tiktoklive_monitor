#!/bin/bash
screen_name=dtap

if [ -z "$STY" ]
then
    # we are not running in screen
    exec screen -dm -S ${screen_name} -L -Logfile dtap_$(date '+%d_%m_%Y_%H_%M_%S').log /bin/bash "$0";
    
else
    # we are running in screen, provide commands to execute

    ./start.sh PROD

fi


