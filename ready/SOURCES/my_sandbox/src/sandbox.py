import json
import uuid
from aiohttp import ClientSession
import asyncio
from aiokafka import AIOKafkaConsumer
from time import sleep
from telebot import util

SPIDERS_DICT = {
    6805: '78.157.221.27',
    6806: '78.157.221.43',
    # 6807: '78.157.221.45',
}


async def listen_kafka(task_id, items, bot, message):
    consumer = AIOKafkaConsumer(
        'data', 'finished',
        loop=asyncio.get_event_loop(),
        bootstrap_servers='78.157.221.27:9091, 78.157.221.43:9091, 78.157.221.45:9091',
        value_deserializer=lambda m: json.loads(m.decode('utf8')))
    await consumer.start()
    async for msg in consumer:
        if msg.topic == 'data':
            if msg.value.get('task_id') == task_id:
                item = msg.value
                text = '{} {}'.format(len(items) + 1,
                                      json.dumps(item, sort_keys=True, indent=4, separators=(",", ": "),
                                                 ensure_ascii=False))
                splitted = util.split_string(text, 3000)
                for text in splitted:
                    bot.send_message(message.chat.id, text, disable_notification=True,
                                     disable_web_page_preview=True)
                    sleep(.3)
                items.append(item)
        elif msg.topic == 'finished':
            if msg.value.get('task_id') == task_id:
                break
    await consumer.stop()


async def process_task(items, bot, msg):
    with open(r'../files/{}_task.json'.format(msg.chat.id), encoding='utf-8') as fp:
        data = json.load(fp)

    task_id = str(uuid.uuid4())

    items_lst = asyncio.ensure_future(listen_kafka(task_id, items, bot, msg))

    data['_task_id'] = task_id

    data['project_id'] = 'metaspider'
    data['spider_id'] = 'metacrawler'

    data['global_settings']['CONCURRENT_REQUESTS'] = 100
    data['global_settings']['CONCURRENT_REQUESTS_PER_DOMAIN'] = 100
    data['global_settings']['AUTOTHROTTLE_TARGET_CONCURRENCY'] = 100
    data['global_settings']['LOG_LEVEL'] = 'DEBUG'
    data['global_settings']['CLOSESPIDER_ITEMCOUNT'] = 100
    data['global_settings']['SCHEDULER_DISK_QUEUE'] = 'scrapy.squeues.PickleLifoDiskQueue'

    # pprint.pprint(data)

    async with ClientSession() as session:
        spider = await get_least_busiest_server_port(session)
        bot.send_message(msg.chat.id, 'send task to {}'.format(spider))
        sleep(.3)
        async with session.post('http://{}/crawl.json'.format(spider), json=data) as response:
            bot.send_message(msg.chat.id, 'task {} sent'.format(task_id))
            sleep(.3)
            with open(r'../files/{}_task.txt'.format(msg.chat.id), 'w') as f:
                f.write(task_id)
            bot.send_message(msg.chat.id, (await response.read()).decode().strip())
            sleep(.3)

    await items_lst

    with open(r'../files/{}_items.json'.format(msg.chat.id), 'w', encoding='utf-8') as fp:
        json.dump(items, fp, ensure_ascii=False)

    sleep(1)
    bot.send_message(msg.chat.id, '{} items saved'.format(len(items)))
    sleep(.3)


async def fetch_status(url, session):
    async with session.get('http://{}/daemonstatus.json'.format(url)) as response:
        data = json.loads((await response.read()).decode().strip())
        data['url'] = url
        return data


async def get_least_busiest_server_port(session):
    tasks = []
    for port, host in SPIDERS_DICT.items():
        task = asyncio.ensure_future(fetch_status('{}:{}'.format(host, port), session))
        tasks.append(task)
    responses = await asyncio.gather(*tasks)
    servers_list = sorted([(r['pending'] + r['running'], r['url']) for r in responses])
    return servers_list[0][1]


def main(bot, msg):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    items = []
    try:
        loop.run_until_complete(process_task(items, bot, msg))
    finally:
        new_items = []
        for data in items:
            new_dict = {'offset': 0, 'partition': 0, 'value': data}
            new_items.append(new_dict)

        with open(r'../files/{}_items.json'.format(msg.chat.id), 'w', encoding='utf-8') as fp:
            json.dump(new_items, fp, ensure_ascii=False)

        with open(r'../files/{}_items.json'.format(msg.chat.id), 'rb') as f:
            bot.send_document(msg.chat.id, f)
            sleep(.3)

        # print('{} items saved'.format(len(items)))
