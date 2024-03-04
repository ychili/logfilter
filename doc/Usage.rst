Usage
=====

.. include:: include/help.txt
   :literal:

Configuration
=============

Create a config file to customize the default values of the script
variables. These values can be overridden by command-line arguments. The
config file should be a series of variable–value pairs, separated by an
equals sign ('='), each on their own line. Whitespace is ignored, and
lines starting with '#' will be ignored as comments.

The XDG configuration directory search path will be searched for config
files named 'logfilter/config'. The search path is based on the values
of environment variables XDG_CONFIG_DIRS and XDG_CONFIG_HOME.
XDG_CONFIG_HOME will be searched first (if unset then this is equal to
'~/.config'), then XDG_CONFIG_DIRS (if unset then this is equal to
'/etc/xdg'). Values in earlier files take precedence over values in
later files. Most regular users should just put their config file at
'~/.config/logfilter/config'.

Variables:

after : date
    Default value of ``--after``
before : date
    Default value of ``--before``
batch : Boolean
    Default setting of ``--batch``
datefmt : format string
    Format of datestamps in log files
level : string
    Default setting of ``--level``
logfiles : path names
    Default value of *FILE* (used if no *FILE*\ s are specified at the
    command line)
program : string
    Program text used by AWK
progfile : path name
    Name of file containing AWK program to use instead of *program*

Built-in defaults:

.. include:: include/defaults.txt
   :literal:

See **date**\ (1) for the accepted format of date and format string
arguments.

Per-logfile configuration
-------------------------

In addition to files named 'logfilter/config', the configuration
directory search path will be searched for files named
'logfilter/logfiles.conf'. This is the per-logfile configuration file.
It contains variable–value pairs like the config file described above,
but each setting must be preceded by a section name in square brackets.
It might look something like this:

::

   [*app.log]
   datefmt = +%Y-%m-%dT%H:%M:%S
   program = $1 > after && $1 <= before && $2 ~ level

If a logfile argument *FILE* matches a section name in a per-logfile
configuration file, then the variable settings in that section will be
used for that file. The remainder of the settings will be taken from
'config' or from the special default section DEFAULT. In the above
example, any logfile matching the filename pattern '\*app.log' will use
the values of **datefmt** and **program** from that section.

See **glob**\ (7) for a description of wildcard matching pathnames.

Setting the variables **logfiles** and **batch** in a section other than
DEFAULT has no effect, because these are program-wide settings.
