app_name=tiktok_mon

while getopts "bcglprs" options
do
  case "${options}" in
    b)
      do_build=y
      ;;
    c)
      do_cleanup=y
      ;;
    g)
      get_conf=y
      ;;
    l)
      view_log=y
      ;;
    p)
      do_build=y
      do_production=y
      ;;
    r)
      do_build=y
      do_run=y
      ;;
    s)
      do_stop=y
      ;;
    :)
      std_err "ERROR: -${OPTARG} requires an argument"
      exit 1
      ;;
    *)
      std_err "ERROR: unknown option ${options}"
      exit 1
      ;;
  esac
done

if [ ! -z "${do_build}" ]
then
    docker stop ${app_name}_container
    docker rm ${app_name}_container
    docker image prune -f
    docker build -t ${app_name} .
fi

if [ ! -z "${do_run}" ]
then
    docker run -d -p 8000:8000 --name ${app_name}_container ${app_name}
fi

if [ ! -z "${do_production}" ]
then
    docker run -d \
        -p 8000:8000 \
        --restart unless-stopped \
        --name ${app_name}_container \
        ${app_name}
fi

if [ ! -z "${view_log}" ]
then
    docker logs -f ${app_name}_container
fi

if [ ! -z "${get_conf}" ]
then
    docker exec ${app_name}_container bash -c "ls /app/streamers_config_*.json" | while read line;
    do
      filenm=$(basename ${line})
      # echo $filenm
      if [ ! -f "${filenm}" ]
      then
        docker cp ${app_name}_container:$line ./;
      else
        echo "Not overwriting file ${filenm}"
      fi
    done
fi

if [ ! -z "${do_stop}" ]
then
    # docker stop ${app_name}_container
    docker exec ${app_name}_container touch /app/stop_monitor.txt
fi

if [ ! -z "${do_cleanup}" ]
then
    echo "Before cleanup:"
    docker system df
    # List and remove unused containers
    # To kill all containers: docker rm $(docker ps -a -q)
    docker ps --filter status=exited --filter status=dead -s
    docker container prune -f
    # Remove images
    docker image prune -a -f
    # To clear the build cache of the default builder
    docker buildx prune -f
    # To remove all unused containers, images, networks, and build cache: docker system prune -af
    echo "After cleanup:"
    docker system df

fi
