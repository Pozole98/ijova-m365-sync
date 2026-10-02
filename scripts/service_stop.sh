#!/usr/bin/env bash
systemctl --user stop ijova-sync.service
systemctl --user status ijova-sync.service --no-pager || true
