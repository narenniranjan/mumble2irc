import asyncio
import markupsafe
import mumble
import pydle
import ssl
import tornado.platform.asyncio
import bs4
import re
import bleach


MUMBLE_USERNAME = 'IRC'
MUMBLE_PASSWORD = 'pw'
MUMBLE_HOST = 'host'
MUMBLE_PORT = 64738
MUMBLE_CHANNEL_ID = 0'

IRC_NICKNAME = 'Mumble'
IRC_HOST = 'host'
IRC_PORT = 6697
IRC_CHANNEL_NAME = '#channel'

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

    def user_moved(self, user, source, dest):
        if source and source == self.me.get_channel():
            self.irc_client.userpart(user.name, self.me.get_channel().name)
        if dest and dest == self.me.get_channel():
            self.irc_client.userjoin(user.name, self.me.get_channel().name) 

    def connection_ready(self):
        self.join_channel(self.channels[MUMBLE_CHANNEL_ID])

    def userjoin(self, joiner, channel):
        self.send_text_message(self.channels[MUMBLE_CHANNEL_ID], "<b>{}</b> has joined {}".format(joiner, channel))

    def userpart(self, joiner, channel, reason):
        self.send_text_message(self.channels[MUMBLE_CHANNEL_ID], "<b>{}</b> has left {} ({})".format(joiner, channel, reason))

    def text_message_received(self, origin, target, message):
        self.irc_client.relay(origin.name, message)

    def relay(self, origin, message):
        self.send_text_message(
            self.channels[MUMBLE_CHANNEL_ID],
            str(markupsafe.Markup('<b>%s:</b> %s') % (origin, markupsafe.Markup(replace_url_to_link(markupsafe.escape(message))))))


class IRCClient(pydle.Client):
    def on_connect(self):
        self.join(IRC_CHANNEL_NAME)

    def on_message(self, source, target, message):
        self.mumble_client.relay(target, message)

    def on_join(self, channel, user):
        if user != self.nickname:
            self.mumble_client.userjoin(user, channel)

    def on_part(self, channel, user, reason):
        if user != self.nickname:
            self.mumble_client.userpart(user, channel, reason)

    def userpart(self, joiner, channel):
        self.message(IRC_CHANNEL_NAME, '<<< \x02{}\x02 has left {}'.format(joiner.replace("", '\u200b'), channel))

    def userjoin(self, joiner, channel):
        joiner = joiner[0] + '\u200b' + joiner[1:]
        self.message(IRC_CHANNEL_NAME, '>>> \x02{}\x02 has joined {}'.format(joiner, channel))

    def relay(self, origin, message):
        origin = origin[0] + '\u200b' + origin[1:]
        self.message(IRC_CHANNEL_NAME, '\x02{}:\x02 {}'.format(extract_text_from_html(origin), extract_text_from_html(message)))


if __name__ == '__main__':
    tornado.platform.asyncio.AsyncIOMainLoop().install()
    loop = asyncio.get_event_loop()

    irc_client = IRCClient(IRC_NICKNAME)
    mumble_client = MumbleClient()

    mumble_client.irc_client = irc_client
    irc_client.mumble_client = mumble_client

    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    irc_client.connect(IRC_HOST, IRC_PORT, tls=True, tls_verify=False)
    loop.run_until_complete(mumble_client.connect(MUMBLE_HOST, MUMBLE_PORT,
                                                  MUMBLE_USERNAME,
                                                  MUMBLE_PASSWORD, ssl_ctx))

    loop.run_forever()

