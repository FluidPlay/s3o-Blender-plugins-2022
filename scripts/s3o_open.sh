#!/bin/bash

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

blender -P ${SCRIPT_DIR}/s3o_open.py -- $1