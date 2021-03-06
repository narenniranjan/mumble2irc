import asyncio
import markupsafe
import mumble
import pydle
import ssl
import tornado.platform.asyncio
import bs4
import re
import configparser
import argparse


def replace_url_to_link(value):
    # Replace url to link 
    urls = re.compile(r"((https?):((//)|(\\\\))+[\w\d:#@%/;$()~_?\+-=\\\.&]*)", re.MULTILINE|re.UNICODE)
    value = urls.sub(r'<a href="\1" target="_blank">\1</a>', value)
    # Replace email to mailto
    urls = re.compile(r"([\w\-\.]+@(\w[\w\-]+\.)+[\w\-]+)", re.MULTILINE|re.UNICODE)
    value = urls.sub(r'<a href="mailto:\1">\1</a>', value)
    return value

def extract_text_from_html(html):
    return bs4.BeautifulSoup(html).text

class MumbleClient(mumble.Client):
    def parse_command(self, message):
        command = message.split(" ")[0]
        if command == ".userlist":
            userstring = ""
            for i in self.irc_client.channels[IRC_CHANNEL_NAME]['users']:
                userstring += i + ", "
            userstring = userstring[0:-2]
            return "<b>Users in {}:</b><br>".format(IRC_CHANNEL_NAME) + str(markupsafe.escape(userstring))
        elif command == ".topic":
            return "<b>Topic for {}:</b><br>".format(IRC_CHANNEL_NAME) + replace_url_to_link(str(markupsafe.escape(self.irc_client.channels[IRC_CHANNEL_NAME]['topic'])))
        else:
            pass

    def user_moved(self, user, source, dest):
        if source and source == self.me.get_channel():
            self.irc_client.userpart(user.name, self.me.get_channel().name)
        if dest and dest == self.me.get_channel():
            self.irc_client.userjoin(user.name, self.me.get_channel().name) 
            try:
                self.send_text_message(
                    self.users_by_name[user.name], self.parse_command('.topic'))
                self.send_text_message(
                    self.users_by_name[user.name], self.parse_command('.userlist'))
            except KeyError as err:
                pass

    def connection_ready(self):
        self.join_channel(self.channels[MUMBLE_CHANNEL_ID])

    def userjoin(self, joiner, channel):
        self.send_text_message(self.channels[MUMBLE_CHANNEL_ID], "<b>{}</b> has joined {}".format(joiner, channel))

    def userpart(self, joiner, channel, reason):
        self.send_text_message(self.channels[MUMBLE_CHANNEL_ID], "<b>{}</b> has left {} ({})".format(joiner, channel, reason))

    def text_message_received(self, origin, target, message):
        if message[0] == '.':
            result_string = self.parse_command(message)
            self.send_text_message(self.users_by_name[origin.name], result_string)
        else:
            self.irc_client.relay(origin.name, message)

    def relay(self, origin, message):
        self.send_text_message(
            self.channels[MUMBLE_CHANNEL_ID],
            "<b>{}:</b> {}".format(origin, replace_url_to_link(str(markupsafe.escape(message)))))


    def irc_action(self, origin, action):
        self.send_text_message(
            self.channels[MUMBLE_CHANNEL_ID],
            "<i>{} {}</i>".format(origin, str(markupsafe.escape(action))))
    
    def nick_change(self, old, new):
        self.send_text_message(
            self.channels[MUMBLE_CHANNEL_ID],
            "<i><b>{}</b> is now known as <b>{}</b></i>".format(str(markupsafe.escape(old)), str(markupsafe.escape(new))))

    def irc_topic(self, channel, message, by):
        self.send_text_message(
            self.channels[MUMBLE_CHANNEL_ID],
            "<b>{}</b> <i>has changed the topic of {} to:</i> {}".format(by, channel, str(markupsafe.escape(message))))

class IRCClient(pydle.Client):
    def parse_command(self, message):
        command = message.split(" ")[0]
        if command == ".userlist":
            userstring = ""
            users = [self.mumble_client.users[x].name for x in self.mumble_client.users if self.mumble_client.users[x].channel_id == MUMBLE_CHANNEL_ID]
            for i in users: 
                userstring += i[0] + '\u00AD' + i[1:] + ", "
            userstring = userstring[0:-2]
            return "\x02Users in {}:\x02 ".format(self.mumble_client.channels[MUMBLE_CHANNEL_ID].name) + str(markupsafe.escape(userstring))
        else:
            pass
    def on_connect(self):
        self.join(IRC_CHANNEL_NAME)

    def on_nick_change(self, old, new):
        self.mumble_client.nick_change(old, new)

    def on_message(self, source, target, message):
        if message[0] == "." and source == IRC_CHANNEL_NAME:
            self.notice(target, self.parse_command(message))
        else:
            self.mumble_client.relay(target, message)

    def on_topic_change(self, channel, message, by):
        self.mumble_client.irc_topic(channel, message, by)

    def on_ctcp_action(self, by, target, contents):
        self.mumble_client.irc_action(by, contents)

    def on_join(self, channel, user):
        if user != self.nickname:
            self.mumble_client.userjoin(user, channel)

    def on_part(self, channel, user, reason):
        if user != self.nickname:
            self.mumble_client.userpart(user, channel, reason)

    def on_quit(self, user, reason):
        if user != self.nickname:
            self.mumble_client.userpart(user, IRC_CHANNEL_NAME, reason)

    def userpart(self, joiner, channel):
        self.message(IRC_CHANNEL_NAME, '<<< \x02{}\x02 has left {}'.format(joiner.replace("", '\u00AD'), channel))

    def userjoin(self, joiner, channel):
        joiner = joiner[0] + '\u00AD' + joiner[1:]
        self.message(IRC_CHANNEL_NAME, '>>> \x02{}\x02 has joined {}'.format(joiner, channel))

    def relay(self, origin, message):
        origin = origin[0] + '\u00AD' + origin[1:]
        self.message(IRC_CHANNEL_NAME, '\x02{}:\x02 {}'.format(extract_text_from_html(origin), extract_text_from_html(message)))


if __name__ == '__main__':
    tornado.platform.asyncio.AsyncIOMainLoop().install()
    loop = asyncio.get_event_loop()

    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--ini', required=False, help='Location of configuration file.')
    args = arg_parser.parse_args()

    config = configparser.ConfigParser()
    if args.ini:
        config.read(args.ini)
    else:
        config.read('relay.ini')

    MUMBLE_CHANNEL_ID = 0
    MUMBLE_PORT = 64738
    MUMBLE_USERNAME = config['Mumble']['nickname']
    MUMBLE_HOST = config['Mumble']['server']
    if 'channel_id' in config['Mumble']:
        MUMBLE_CHANNEL_ID = int(config['Mumble']['channel_id'])
    if 'password' in config['Mumble']:
        MUMBLE_PASSWORD = config['Mumble']['password']
    if 'port' in config['Mumble']:
        MUMBLE_PORT = config['Mumble']['port']
    if 'cert' in config['Mumble']:
        MUMBLE_CERT_FILE = config['Mumble']['cert']
        MUMBLE_CERT_PW = config['Mumble']['certpw']

    IRC_PORT = 6667
    IRC_NICKNAME = config['IRC']['nickname']
    IRC_HOST = config['IRC']['server']
    IRC_CHANNEL_NAME = config['IRC']['channel']
    if 'port' in config['IRC']:
        IRC_PORT = config['IRC']['port']


    irc_client = IRCClient(IRC_NICKNAME)
    mumble_client = MumbleClient()

    mumble_client.irc_client = irc_client
    irc_client.mumble_client = mumble_client

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    if MUMBLE_CERT_FILE and MUMBLE_CERT_PW:
        ssl_ctx.load_cert_chain(MUMBLE_CERT_FILE, None, MUMBLE_CERT_PW)

    irc_client.connect(IRC_HOST, IRC_PORT, tls=True, tls_verify=False)
    loop.run_until_complete(mumble_client.connect(MUMBLE_HOST, MUMBLE_PORT,
                                                  MUMBLE_USERNAME,
                                                  MUMBLE_PASSWORD, ssl_ctx))

    loop.run_forever()

