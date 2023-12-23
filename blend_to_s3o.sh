#!/bin/bash
# Usage: ./blend_to_s3o.sh <folder_with_.blend> <output_s3o_folder>

if [[ -z "$1" ]] || [[ -z "$2" ]]; then
    echo "Usage: ./blend_to_s3o.sh <folder_with_.blend> <output_s3o_folder>"
    exit 1
fi

export SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
export EXPORT_DIR="${2}"

find "${1}" -maxdepth 1 -iname '*.blend' -print0 | xargs -0 -I {} -P $(nproc) /bin/bash -c '
    file=$(basename $1)
    DEST="${EXPORT_DIR}/${file:0:-6}.s3o"
    if [[ ! -f ${DEST} ]]; then
        blender $1 -b -P ${SCRIPT_DIR}/scripts/s3o_from_blend.py -- ${DEST}; 
    fi
' '_' {}