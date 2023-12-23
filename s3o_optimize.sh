#!/bin/bash

if [[ -z "$1" ]]; then
    echo "Usage: ./s3o_optimize.sh <folder_with_.s3o>"
    exit 1
fi

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

find "${1}" -maxdepth 1 -iname '*.s3o' -print0 | xargs -0 -I {} -P $(nproc) blender -b -P ${SCRIPT_DIR}/scripts/s3o_optimize.py -- "{}"
