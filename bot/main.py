import asyncio
import logging
import os
import sys
import re

from dataclasses import dataclass
from http import HTTPStatus
from pprint import pformat

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, StateFilter
from aiohttp.client import ClientSession
from aiogram.utils.keyboard import InlineKeyboardBuilder

BUILDER = InlineKeyboardBuilder()
BUILDER.row(
    types.InlineKeyboardButton(text="Статус сервера", callback_data="server_status"),
    types.InlineKeyboardButton(text="Новый timestamp", callback_data="new_post")
)
BUILDER.row(
    types.InlineKeyboardButton(text="Найти собак по породе", callback_data="find_dogs"),
    types.InlineKeyboardButton(text="Добавить собаку в базу", callback_data="create_dog")
)
BUILDER.row(
    types.InlineKeyboardButton(text="Найти собаку", callback_data="find_dog"),
    types.InlineKeyboardButton(text="Обновить данные собаки", callback_data="update_dog")
)
MARKUP = BUILDER.as_markup()


class Request(StatesGroup):
    find_dogs = State()
    create_dog = State()
    find_dog = State()
    update_dog = State()


@dataclass
class Config:
    token: str
    api_url: str

    @classmethod
    def from_env(cls) -> 'Config':
        token = os.getenv('BOT_TOKEN')
        if not token:
            raise ValueError('Please, set BOT_TOKEN')

        api_url = os.getenv('BOT_API_URL')
        if not api_url:
            raise ValueError('Please, set BOT_API_URL')

        return Config(token, api_url)


def configure_logging():
    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='[%(asctime)s] %(levelname)-8s %(name)-12s %(message)s',
        stream=sys.stdout,
        force=True,
    )


async def http_request(callback, httpclient, method, url, params='', json=None):
    if json is None:
        json = dict()
    async with httpclient.request(method, url, params=params, json=json) as response:
        if response.status == HTTPStatus.OK:
            return await response.json()

        if 400 <= response.status < 500:
            answer = await response.json()
            await callback.answer(f'Получена ошибка от API:\n {pformat(answer)}', reply_markup=MARKUP)

        if response.status >= 500:
            await callback.answer(f'Ошибка на сервере, повторите попытку позже', reply_markup=MARKUP)


def format_answer(answer):
    print(answer)
    return f"name: {answer['name']}, pk: {answer['pk']}, kind: {answer['kind']}"


DOG_TYPES = ['terrier', 'bulldog', 'dalmatian']


dp = Dispatcher()


@dp.callback_query(F.data == "server_status")
async def send_server_status(callback: types.CallbackQuery, httpclient: ClientSession):
    answer = await http_request(callback.message, httpclient, 'get', '/')
    if answer is not None:
        await callback.message.answer(answer)


@dp.callback_query(F.data == "new_post")
async def send_new_post(callback: types.CallbackQuery, httpclient: ClientSession):
    answer = await http_request(callback.message, httpclient, 'post', '/post')
    if answer is not None:
        await callback.message.answer(text=f"id: {answer['id']}, timestamp: {answer['timestamp']}")


@dp.callback_query(F.data == "find_dogs")
async def find_dogs(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Request.find_dogs.state)
    await callback.message.answer(text=f'Необходимо выбрать один из вариантов: {", ".join(DOG_TYPES)}')


@dp.message(StateFilter(Request.find_dogs), lambda message: message.text.lower() in DOG_TYPES)
async def send_dogs(message: types.Message, httpclient: ClientSession, state: FSMContext):
    answer = await http_request(message, httpclient, 'get', '/dog', f'kind={message.text.lower()}')
    if answer is not None:
        text = '\n'.join(format_answer(item) for item in answer)
        await message.answer(text=text, reply_markup=MARKUP)
    await state.clear()


@dp.callback_query(F.data == "create_dog")
async def create_dog(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Request.create_dog.state)
    example = f"\"name: <кличка_вашей_собаки>, pk: <уникальный_идентификатор>, kind: <{'_или_'.join(DOG_TYPES)}>\""
    await callback.message.answer(text=f'Необходимо заполнить данные собаки в следующем формате: {example}\nПример: name: Name, pk: 12, kind: dalmatian')


@dp.message(StateFilter(Request.create_dog), lambda message: re.findall(r"name: (\w+), pk: (\d+), kind: (terrier|bulldog|dalmatian)", message.text.lower()))
async def send_created_dog(message: types.Message, httpclient: ClientSession, state: FSMContext):
    match = re.search(r"name: (\w+), pk: (\d+), kind: (terrier|bulldog|dalmatian)", message.text.lower())
    answer = await http_request(message, httpclient, 'post', '/dog', json={'name': match.group(1), 'pk': match.group(2), 'kind': match.group(3)})
    if answer is not None:
        text = format_answer(answer)
        await message.answer(text=f'Добавили: {text}', reply_markup=MARKUP)
    await state.clear()


@dp.callback_query(F.data == "find_dog")
async def find_dog(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Request.find_dog.state)
    await callback.message.answer(text=f'Необходимо ввести pk собаки.')


@dp.message(StateFilter(Request.find_dog), lambda message: message.text.isdigit())
async def send_found_dogs(message: types.Message, httpclient: ClientSession, state: FSMContext):
    answer = await http_request(message, httpclient, 'get', f'/dog/{message.text}')
    if answer is not None:
        text = format_answer(answer)
        await message.answer(text=f'Нашли: {text}', reply_markup=MARKUP)
    await state.clear()


@dp.callback_query(F.data == "update_dog")
async def update_dog(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Request.update_dog.state)
    example = f"\"old_pk: <старый_идентификатор>, name: <кличка_вашей_собаки>, pk: <новый_или_старый_уникальный_идентификатор>, kind: <{'_или_'.join(DOG_TYPES)}>\""
    await callback.message.answer(text=f'Необходимо заполнить новые данные собаки в следующем формате: {example}\nПример: name: Name, pk: 12, kind: dalmatian')


@dp.message(StateFilter(Request.update_dog), lambda message: re.findall(r"old_pk: (\d+), name: (\w+), pk: (\d+), kind: (terrier|bulldog|dalmatian)", message.text.lower()))
async def send_updated_dog(message: types.Message, httpclient: ClientSession, state: FSMContext):
    match = re.search(r"old_pk: (\d+), name: (\w+), pk: (\d+), kind: (terrier|bulldog|dalmatian)", message.text.lower())
    answer = await http_request(message, httpclient, 'patch', f'/dog/{match.group(1)}', json={'name': match.group(2), 'pk': match.group(3), 'kind': match.group(4)})
    if answer is not None:
        text = format_answer(answer)
        await message.answer(text=f'Обновили: {text}', reply_markup=MARKUP)
    await state.clear()


@dp.message(CommandStart())
async def handle_start(message: types.Message):
    text = f'Здравствуйте, {message.from_user.full_name}, рад, что Вы здесь! Что бы Вы хотели сделать?'
    await message.answer(text=text, reply_markup=MARKUP)


async def main():
    configure_logging()
    config = Config.from_env()
    bot = Bot(config.token)
    session = ClientSession(base_url=config.api_url)
    async with session as aiohttp_client:
        await dp.start_polling(bot, httpclient=aiohttp_client, close_bot_session=True)

if __name__ == '__main__':
    asyncio.run(main())
