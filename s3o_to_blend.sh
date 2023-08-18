#!/bin/bash

if [[ -z "$1" ]] || [[ -z "$2" ]]; then
    echo "Usage: ./s3o_to_blend.sh <folder_with_.s3o> <output_.blend_folder>"
    exit 1
fi

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

blender -b -P ${SCRIPT_DIR}/scripts/s3o_to_blend.py -- "${1}" "${2}";