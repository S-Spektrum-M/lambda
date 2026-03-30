#!/bin/sh
git add -A && git commit -m "${1:-update blog}" && git push
