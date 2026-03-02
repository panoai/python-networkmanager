# Reads the Networkmanager headers and spits out the enums as a series of
# python variables.

import os
import re

enum_regex = re.compile(r'typedef enum(?:\s+[a-zA-Z]+)?\s*\{(.*?)\}', re.DOTALL)
comment_regex = re.compile(r'/\*.*?\*/', re.DOTALL)
headers = [
    '/usr/include/libnm/nm-dbus-interface.h',
    # VPN constants: legacy first so modern libnm values win
    '/usr/include/NetworkManager/NetworkManagerVPN.h',
    '/usr/include/libnm/nm-vpn-dbus-interface.h',
    # SecretAgent constants: legacy first so modern libnm values win
    '/usr/include/libnm-glib/nm-secret-agent.h',
    '/usr/include/libnm/nm-errors.h',
]

names = {}
for h in headers:
    if not os.path.exists(h):
        continue
    with open(h) as f:
        source = comment_regex.sub('', f.read())
    for enum in enum_regex.findall(source):
        last = -1
        for key in enum.split(','):
            if not key.strip():
                continue
            if '=' in key:
                key, val = key.split('=')
                val = eval(val.replace('LL',''), names)  # noqa: S307
            else:
                val = last + 1
            key = key.strip()
            names[key] = val
            print('%s = %d' % (key, val))
            last = val
