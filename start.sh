#!/bin/bash
virt_env=tiktok
env_type=${1}
python_version=3.12.3

if [ "$(uname)" == "Darwin" ]
then
    conda_shell=/opt/homebrew/Caskroom/miniconda/base/etc/profile.d/conda.sh

    if [ "${CONDA_DEFAULT_ENV} " != "${virt_env} " ]
    then
        source ${conda_shell}
        if ! conda env list | grep ${virt_env} > /dev/null
        then
            conda create -n ${virt_env} python==${python_version} -y
        fi
        conda activate ${virt_env} || exit 1
    fi
elif [ "$(uname)" == "Linux" ]
then
    if [ ! -d ""./${virt_env}" "]
    then
        python3 -m venv ${virt_env}
        source ${virt_env}/bin/activate
    elif [[ ! "${VIRTUAL_ENV} " == *"${virt_env} " ]]
    then
        source ${virt_env}/bin/activate
    fi
else
    echo "Env $(uname) not supported"
    exit 1
fi

pip install -r ./requirements.txt

exec_command=''


if [ ! -f ./.api_key ]
then
    echo "File .api_key missing"
else
    exec_command='SIGN_API_KEY=$(cat ./.api_key)'
fi

exec_command="${exec_command} python main.py"

if [ ! "${env_type} " == "PROD " ]
then
    exec_command="${exec_command} --test"
fi

exec_command="${exec_command} --config streamers_config.json"

echo "Executing ${exec_command}"

eval "${exec_command}"



