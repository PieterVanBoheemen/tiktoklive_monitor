#!/bin/bash
db_file=master.sqlite3.json
media_file=media.tar.gz
local_bk_dir=/Users/SB/Projects/Software/Stichting/devopsDTAP/bk_dir
root_dest_dir=/Users/SB/Projects/Software/Stichting
current_db=${db_file}.current
current_media=${media_file}.current

do_import=n

while getopts "i" options
do
  case "${options}" in
    i)
      do_import=y
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

if [ ${do_import} == 'y' ]
then
    echo "importing from backup"
    media_dir=${root_dest_dir}/media/
    if [ -d "${media_dir}" ]
    then
        rm -r "${media_dir}"
    fi
    mkdir "${media_dir}"
    tar -xzvf ${local_bk_dir}/media.tar.gz.current -C "${root_dest_dir}"

    cp "${local_bk_dir}/${current_db}" "${root_dest_dir}/dtap/${db_file}"
fi

./start.sh DEV

if [ -f "${root_dest_dir}/dtap/${db_file}" ]
then
    rm "${root_dest_dir}/dtap/${db_file}"
fi