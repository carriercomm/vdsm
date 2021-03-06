#
# Copyright 2014 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA
#
# Refer to the README and COPYING files for full details of the license
#

"""
This module provides cpu profiling.
"""

from functools import wraps
import logging
import os
import threading

from vdsm import constants
from vdsm.config import config

from .errors import UsageError

# Import yappi lazily when profile is started
yappi = None

# Defaults

_FILENAME = os.path.join(constants.P_VDSM_RUN, 'vdsmd.prof')
_FORMAT = config.get('devel', 'cpu_profile_format')
_BUILTINS = config.getboolean('devel', 'cpu_profile_builtins')
_CLOCK = config.get('devel', 'cpu_profile_clock')
_THREADS = True

_lock = threading.Lock()


def start():
    """ Starts application wide CPU profiling """
    if is_enabled():
        _start_profiling(_CLOCK, _BUILTINS, _THREADS)


def stop():
    """ Stops application wide CPU profiling """
    if is_enabled():
        _stop_profiling(_FILENAME, _FORMAT)


def is_enabled():
    return config.getboolean('devel', 'cpu_profile_enable')


def is_running():
    with _lock:
        return yappi and yappi.is_running()


def profile(filename, format=_FORMAT, clock=_CLOCK, builtins=_BUILTINS,
            threads=_THREADS):
    """
    Profile decorated function, saving profile to filename using format.

    Note: you cannot use this when the application wide profile is enabled, or
    profile multiple functions in the same code path.
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*a, **kw):
            _start_profiling(clock, builtins, threads)
            try:
                return f(*a, **kw)
            finally:
                _stop_profiling(filename, format)
        return wrapper
    return decorator


def _start_profiling(clock, builtins, threads):
    global yappi
    logging.debug("Starting CPU profiling")

    import yappi

    with _lock:
        # yappi start semantics are a bit too liberal, returning success if
        # yappi is already started, happily having too different code paths
        # that thinks they own the single process profiler.
        if yappi.is_running():
            raise UsageError('CPU profiler is already running')
        yappi.set_clock_type(clock)
        yappi.start(builtins=builtins, profile_threads=threads)


def _stop_profiling(filename, format):
    logging.debug("Stopping CPU profiling")
    with _lock:
        if yappi.is_running():
            yappi.stop()
            stats = yappi.get_func_stats()
            stats.save(filename, format)
            yappi.clear_stats()
