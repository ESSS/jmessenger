"""Example of using hangups.build_user_conversation_list to data."""

import appdirs
import asyncio

import hangups
from hangups.ui.utils import get_conv_name
from hangups import ChatMessageSegment
import os


def text_to_segments(text):
    """Create list of message segments from text"""
    return ChatMessageSegment.from_str(text)


#===================================================================================================
# JenkinsMessenger
#===================================================================================================
class JenkinsMessenger(object):
    
    def __init__(self):

        self.started_jobs = {}
        self.conversations = {}

        dirs = appdirs.AppDirs('hangups', 'hangups')
        default_token_path = os.path.join(dirs.user_cache_dir, 'refresh_token.txt')
        cookies = hangups.auth.get_auth_stdin(default_token_path)
        
        self._client = hangups.Client(cookies)
        self._client.on_connect.add_observer(self._on_connect)
        self._client.on_disconnect.add_observer(self._on_disconnect)

        # Start asyncio event loop and connect to Hangouts
        # If we are forcefully disconnected, try connecting again
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self._client.connect())


    def list_conversations(self):
        """List all active conversations"""
        convs = sorted(self._conv_list.get_all(),
                       reverse=True, key=lambda c: c.last_modified)
        return convs


    @asyncio.coroutine
    def _on_connect(self):
        """Handle connecting for the first time"""
        print('Connected!')
        self._retry = 0
        self._user_list, self._conv_list = (
            yield from hangups.build_user_conversation_list(self._client)
        )
        self._conv_list.on_event.add_observer(self._on_event)

        print(('Conversations:'))
        name_to_jenkins_user_id = {
            'Tiago Nobrega' : 'tnobrega',
            'Marcos Cabral Damiani' : 'damiani',
            'Fabio Zadrozny' : 'fabioz',
            'Gabriel Maicon Marcílio' : 'gabrielm',
        }
        for c in self.list_conversations():
            c_name = get_conv_name(c, truncate=True)
            if c_name in name_to_jenkins_user_id:
                user_id = name_to_jenkins_user_id[c_name]
                self.conversations[user_id] = c
                print('  Linking: {} -> {}({})'.format(user_id, c_name, c.id_))
            else:
                print('  {} ({})'.format(c_name, c.id_))
                for user in c.users:
                    print('  {} {}'.format(user, user.emails))

        while True:
            self.update_jobs()
            yield from asyncio.sleep(5)
#             self.send_message(c, 'Looping: ' + str(i))

        print()

    def get_build_str(self, last_build_info, last_build_errors=None):
        build_str = ''
        
        result = last_build_info.get('result')
        if result:
            build_str += '* Result: **{}**\n'.format(result)
            
        result = last_build_info.get('took')
        if result:
            build_str += '* Duration: **{}**\n'.format(result)

        result = last_build_info.get('builtOn')
        if result:
            build_str += '* Built On: **{}**\n'.format(result)

        result = last_build_info.get('timestamp')
        if result:
            build_str += '* Started: **{}**\n'.format(result)

#         for k, v in last_build_info.items():
#             if k not in ['_class']:
#                 build_str += '\t {}: {}\n'.format(k, v)

        if last_build_errors is not None and len(last_build_errors) > 0:
            build_str += 'Errors: {}\n'.format(len(last_build_errors))
            for error in last_build_errors:
                build_str += '{}\n'.format(error['name'])
                if 'className' in error:
                    build_str += '\t{}\n'.format(error['className'])

        return build_str

    def send_build_message(self, status, job_name, last_build, last_build_errors=None):
        user_id = last_build.get('userId')
        print('send_build_message:', user_id)
        if user_id in self.conversations:
            print(status, job_name)
            print(self.get_build_str(last_build))
            msg = '-' * 80
            msg += '\n**{}**: {}\n{}'.format(status, job_name, self.get_build_str(last_build, last_build_errors))
            self.send_message(self.conversations[user_id], msg)

    def on_job_start(self, job_name, last_build):
        self.send_build_message('Started', job_name, last_build)

    def on_job_finished(self, job_name, last_build, last_build_errors):
        print('on_job_finished', job_name)
        self.send_build_message('Finished', job_name, last_build, last_build_errors)

    def update_jobs(self):
        from jenkins_jobs import get_building_jobs, get_job_last_build, get_last_build_errors

        building_jobs = get_building_jobs()
        for job_name, last_build in building_jobs.items():
            if job_name not in self.started_jobs:
                self.on_job_start(job_name, last_build)

        finished_jobs = []
        for job_name, started_build in list(self.started_jobs.items()):
            if job_name not in building_jobs:
                finished_jobs.append(job_name)
                self.started_jobs.pop(job_name)

        for job_name in finished_jobs:
            last_build_info = get_job_last_build(job_name)
            last_build_errors = get_last_build_errors(job_name)
            self.on_job_finished(job_name, last_build_info, last_build_errors)
#             for k, v in last_build_info.items():
#                 if k not in ['_class']:
#                     print('\t', k, v)
#                     
#             if last_build_info['result'] != 'SUCCESS':
#                 for error in get_last_build_errors(job_name):
#                     print(error)

        self.started_jobs = building_jobs


    @asyncio.coroutine
    def _on_event(self, conv_event):
        """Handle conversation events"""
        print('_on_event')
#         yield from handler.handle(self, conv_event)

    @asyncio.coroutine
    def _on_disconnect(self):
        """Handle disconnecting"""
        print(('Connection lost!'))


    def _on_message_sent(self, future):
        """Handle showing an error if a message fails to send"""
        try:
            future.result()
        except hangups.NetworkError:
            print(_('Failed to send message!'))


    def send_message(self, conversation, text):
        """Send simple chat message"""
        self.send_message_segments(conversation, text_to_segments(text))


    def send_message_segments(self, conversation, segments):
        """Send chat message segments"""
        # Ignore if the user hasn't typed a message.
        if len(segments) == 0:
            return
        # XXX: Exception handling here is still a bit broken. Uncaught
        # exceptions in _on_message_sent will only be logged.
        asyncio.async(
            conversation.send_message(segments)
        ).add_done_callback(self._on_message_sent)



if __name__ == '__main__':
    messenger = JenkinsMessenger()
