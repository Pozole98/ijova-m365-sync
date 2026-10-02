#!/usr/bin/env bash
systemctl --user restart ijova-sync.service
systemctl --user status ijova-sync.service --no-pager
