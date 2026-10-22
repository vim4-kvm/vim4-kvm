#!/bin/sh
# Install only the logging policy, without restarting KVM or USB services.
set -eu
cd "$(dirname "$0")"
install -D -m 0644 60-vim4-journal.conf /usr/lib/systemd/journald.conf.d/60-vim4-journal.conf
install -D -m 0755 vim4-logging /usr/libexec/vim4-logging
/usr/libexec/vim4-logging
