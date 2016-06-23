#!/usr/bin/env bash

# Show disk use for directories whose files are more than 1GB

sudo du -h / | grep -P '^[0-9\.]+G'
