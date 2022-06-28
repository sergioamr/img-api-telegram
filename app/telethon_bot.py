import os
import sys
import time
import json

from .print_helper import *

from telethon.sync import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import Channel, MessageMediaDocument
from telethon.tl.functions.messages import GetHistoryRequest

from app.file_helper import ensure_dir

galleries = {}


class Telethon_Integration():
    client = None
    cfg = None
    imgapi = None
    state = {}

    def read_state(self):
        try:
            state_path = self.cfg.get('state_path', "imgapi_state.json")

            with open(state_path, 'r') as f:
                self.state = json.load(f)

        except Exception as e:
            return {}

    def save_state(self):
        state_path = self.cfg.get('state_path', "imgapi_state.json")

        with open(state_path, 'w', encoding='utf-8') as f:
            json.dump(self.cfg, f, ensure_ascii=False, indent=4)

    def save_key_value(self, key, value):
        self.state[key] = value
        self.save_state()

    def __init__(self, client, imgapi, cfg):
        self.client = client
        self.imgapi = imgapi
        self.cfg = cfg
        self.read_state()

    def get_gallery(self, telegram_id, telegram_name, telegram_title, telegram_username):
        tid = telegram_id
        if tid in galleries:
            return galleries[tid]

        gallery_def = {
            "title": telegram_name,
            "header": telegram_title,
            "my_telegram_id": telegram_id,
            "my_telegram_username": telegram_username,
            "is_public": True,
            "tags": [ "telegram", telegram_username ]
        }

        ret = self.imgapi.create_gallery(gallery_def)

        if 'galleries' not in self.state:
            self.state['galleries'] = {}

        if 'galleries' in ret:
            gallery = ret['galleries'][0]
            self.state['galleries'][tid] = gallery

            print_b('BOT', " Gallery " + gallery['name'])
            return gallery

        self.state['galleries'][tid] = ret
        return ret

    def get_gallery_id(self, telegram_id, telegram_title):
        gallery = self.get_gallery(telegram_id, telegram_title)
        gid = gallery and gallery['id'] if 'id' in gallery else None
        return gid

    def fetch_all_channel(self, my_channel, gallery, channel='t.me/oinktv'):
        if not my_channel:
            my_channel = self.client.get_entity(channel)

        # Check if user is in channel
        #self.client(JoinChannelRequest(my_channel))

        if not gallery:
            gallery_id = None
        else:
            gallery_id = gallery['id']

        found_media = {}

        limit = 50

        channel_name = my_channel.name
        channel_folder = "data/" + channel_name
        ensure_dir(channel_folder)

        offset_id = 0
        #if 'last_message_id' in self.state:
        #    offset_id = self.state['last_message_id']

        b_exit = False
        while not b_exit:
            messages = self.client.get_messages(my_channel,
                                                limit=limit,
                                                offset_id=offset_id)

            for msg in messages:
                # Format the message content

                if getattr(msg, 'media', None):
                    print(str(msg.date) + " Found media id " + str(msg.id))

                    found_media[msg.id] = msg

                    media_folder = channel_folder + "/" + str(msg.id) + "/"
                    if os.path.exists(media_folder):
                        print_h1("Finished fetching " + media_folder)
                        return

                    ensure_dir(media_folder)
                    media = msg.media

                    try:
                        mime = media.document.mime_type.lower()
                        path = self.client.download_media(msg, media_folder)

                        print("+ Media: " + mime)
                        print("+ Path: " + path)

                        res = self.imgapi.api_check_md5(path)
                        if not 'media_files' in res:
                            print_b("Upload")
                            json_res = self.imgapi.api_upload(
                                [path], gallery_id=gallery_id)
                            time.sleep(1)
                        else:
                            print_r("Duplicated")
                            sys.exit()

                        os.remove(path)

                        offset_id = messages[-1].id

                        # self.state['galleries'][gallery_id]['last_message_id'] = msg.id
                        # self.save_state()

                    except Exception as e:
                        print(" Fialed uploading video ")

                    content = '<{}> {}'.format(
                        type(msg.media).__name__, msg.message)

                elif hasattr(msg, 'message'):
                    content = msg.message
                elif hasattr(msg, 'action'):
                    content = str(msg.action)
                else:
                    # Unknown message, simply print its class name
                    content = type(msg).__name__

            time.sleep(5)

    def check_galleries(self):
        """ Downloads and checks if we have all the galleries and groups that this telethon user is subscribed """
        for dialog in self.client.iter_dialogs():
            if not dialog.is_channel and not dialog.is_group:
                continue

            print(f'{dialog.id} {dialog.title} {dialog.entity.username} ')

            gallery = self.get_gallery(dialog.id, dialog.name, dialog.title, dialog.entity.username)

            if gallery:
                self.fetch_all_channel(dialog, gallery)



def telegram_init(cfg, imgapi):
    client = TelegramClient('name', cfg['API_ID'], cfg['API_HASH'])

    client.connect()
    if not client.is_user_authorized():
        phone_number = cfg['PHONE_NUMBER']
        client.send_code_request(phone_number)
        myself = client.sign_in(phone_number, input('Enter code: '))

    client.send_message('me', 'Booting system!')

    @client.on(events.NewMessage(pattern='(?i).*Hello'))
    async def handler(event):
        await event.reply('Hey!')

    telethon = Telethon_Integration(client, imgapi, cfg)
    telethon.check_galleries()

    print_b(" TEST ")
