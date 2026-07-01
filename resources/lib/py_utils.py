# -*- coding: utf-8 -*-
# Copyright: (c) 2016, SylvainCecchetto
# GNU General Public License v2.0+ (see LICENSE.txt or https://www.gnu.org/licenses/gpl-2.0.txt)

# This file is part of Catch-up TV & More

from __future__ import unicode_literals

import datetime
import hashlib
import numbers
import time


try:
    from zoneinfo import ZoneInfo
except ImportError:
    try:
        # python < 3.9
        from backports.zoneinfo import ZoneInfo
    except ImportError:
        # python 2.7 (Kodi 18): neither zoneinfo nor backports.zoneinfo are
        # available. Fall back to pytz, exposing the same ZoneInfo(name) API.
        import pytz

        def ZoneInfo(key):
            """pytz-backed drop-in for zoneinfo.ZoneInfo on Python 2.7.

            Raises ValueError for an unknown/empty time zone name so that
            callers can handle it the same way as the stdlib implementation.
            """
            try:
                return pytz.timezone(key)
            except Exception:
                raise ValueError(key)


def old_div(a, b):
    """Python 2 and 3 Integer division cheat (https://python-future.org/compatible_idioms.html#division)

    """
    if isinstance(a, numbers.Integral) and isinstance(b, numbers.Integral):
        return a // b

    return a / b


def current_timestamp():
    """Get current timestamp (Unix time, the same given here https://timestamp.online)

    Returns:
        float: Current timestamp
    """
    return time.time()


def compute_md5(filepath):
    """Compute MD5 hash of file given by filepath.

    Args:
        filepath (str)
    Returns:
        str: MD5 value of the file given by filepath
    """
    with open(filepath, "rb") as f:
        file_md5 = hashlib.md5()
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            file_md5.update(chunk)

        return file_md5.hexdigest()


def datetime_strptime(s, f):
    """Simple workaroung to fix https://forum.kodi.tv/showthread.php?tid=112916

    """
    try:
        return datetime.datetime.strptime(s, f)
    except TypeError:
        return datetime.datetime(*(time.strptime(s, f)[0:6]))
