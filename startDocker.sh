app_name=tiktok_mon

while getopts "blprs" options
do
  case "${options}" in
    b)
      do_build=y
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


if [ ! -z "${do_stop}" ]
then
    # docker stop ${app_name}_container
    docker exec ${app_name}_container touch /app/stop_monitor.txt
fi

