#!/bin/bash

# Install: sudo ln -s $PWD/s3o_open.sh /usr/local/bin/blender-s3o

SCRIPT_DIR=$( cd -P "$( dirname $( readlink "${BASH_SOURCE[0]}" ) )" >/dev/null 2>&1 && pwd )

if [[ ! -f "$1" ]]; then
    echo "Usage: blender-s3o <file.s3o>"
    exit 1
fi

blender -P ${SCRIPT_DIR}/s3o_open.py -- $1