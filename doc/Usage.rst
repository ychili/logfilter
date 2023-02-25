Usage
-----

.. include:: include/help.txt
   :literal:

Configuration
-------------

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

Built-in defaults:

.. include:: include/defaults.txt
   :literal:

See **date**\ (1) for the accepted format of date and format string
arguments.
