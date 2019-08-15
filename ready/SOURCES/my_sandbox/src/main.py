from sandbox import main as sandbox_start
from telebot import TeleBot, apihelper
from configparser import ConfigParser
from requests import post
import json

cfg = ConfigParser()
cfg.read('../res/config.ini')
apihelper.proxy = {'https': 'socks5h://{user}:{pwd}@{ip}:{port}'.format(**cfg['Proxy'])}
bot = TeleBot(cfg['Telegram']['secret'])


@bot.message_handler(commands=['start'])
def start(msg):
    bot.reply_to(msg, 'Пришли мне task.json. В ответ будут приходить сообщения от kafka. В конце я пришлю тебе items.json')


@bot.message_handler(commands=['run', 'sandbox'])
def start_sandbox(msg):
    sandbox_start(bot, msg)
    bot.send_message(msg.chat.id, "Successfully finished")


@bot.message_handler(commands=['stop'])
def stop(msg):
    try:
        with open(r'../files/{}_task.txt'.format(msg.chat.id)) as f:
            task_id = f.read()

        r = json.dumps(json.loads(post('http://10.199.13.39:8181/cancel',
                                       json={"_task_id": task_id, "force": True},
                                       headers={'Content-Type': 'application/json'}).text), sort_keys=True, indent=4,
                       separators=(",", ": "),
                       ensure_ascii=False)
        bot.send_message(msg.chat.id, r)
    except Exception as e:
        bot.send_message(msg.chat.id, f'{e.__class__.__name__}: {e}')


@bot.message_handler(content_types=['document'])
def document(msg):
    file_info = bot.get_file(msg.document.file_id)
    file = bot.download_file(file_info.file_path)
    with open('../files/{}_task.json'.format(msg.chat.id), 'wb') as f:
        f.write(file)
    sandbox_start(bot, msg)


def run():
    try:
        print('Polling...')
        bot.polling()
    except:
        run()


run()
