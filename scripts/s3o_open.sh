#!/bin/bash

# Install: sudo ln -s $PWD/s3o_open.sh /usr/local/bin/blender-s3o

SOURCE=${BASH_SOURCE[0]}
while [ -L "$SOURCE" ]; do # resolve $SOURCE until the file is no longer a symlink
  DIR=$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )
  SOURCE=$(readlink "$SOURCE")
  [[ $SOURCE != /* ]] && SOURCE=$DIR/$SOURCE # if $SOURCE was a relative symlink, we need to resolve it relative to the path where the symlink file was located
done
SCRIPT_DIR=$( cd -P "$( dirname "$SOURCE" )" >/dev/null 2>&1 && pwd )

if [[ ! -f "$1" ]]; then
    echo "Usage: blender-s3o <file.s3o>"
    exit 1
fi

blender -P ${SCRIPT_DIR}/s3o_open.py -- $1