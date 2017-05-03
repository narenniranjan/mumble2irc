# mumble2irc: A mumble to IRC relay bot

This project has been superceded by https://github.com/narenniranjan/broadcast.

# Requirements:

* python-mumble (from rfw/python-mumble)
* python3.5 (as python-mumble is a python3.5 project)
* pydle (from shizmob/pydle)

# Running the bot:
Note that --ini is an optional argument, and if given no arguments the bot reads configuration from relay.ini.

    $EDITOR relay.ini 
    python3.5 relay-bot.py (--ini /path/to/ini/file)
