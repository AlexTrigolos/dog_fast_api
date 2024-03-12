import datetime
import uvicorn

from enum import Enum
from typing import List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from redis import asyncio as aioredis
from fastapi_cache import FastAPICache
from fastapi_cache.decorator import cache
from fastapi_cache.backends.redis import RedisBackend

app = FastAPI(title='Dog API')


class DogType(str, Enum):
    terrier = "terrier"
    bulldog = "bulldog"
    dalmatian = "dalmatian"


class Dog(BaseModel):
    name: str
    pk: int
    kind: DogType


class Timestamp(BaseModel):
    id: int
    timestamp: int


dogs_db = {
    0: Dog(name='Bob', pk=0, kind='terrier'),
    1: Dog(name='Marli', pk=1, kind="bulldog"),
    2: Dog(name='Snoopy', pk=2, kind='dalmatian'),
    3: Dog(name='Rex', pk=3, kind='terrier'),
    4: Dog(name='Pongo', pk=4, kind='dalmatian'),
    5: Dog(name='Tillman', pk=5, kind='terrier'),
    6: Dog(name='Uga', pk=6, kind='bulldog')
}

post_db = [
    Timestamp(id=0, timestamp=12),
    Timestamp(id=1, timestamp=10)
]


@app.get('/')
def root():
    return 'OK'


@app.post('/post', response_model=Timestamp, summary='Get Post')
def create_and_take_post():
    post_db.append(Timestamp(id=(post_db[-1].id + 1 or 0), timestamp=int(datetime.datetime.now().timestamp())))
    return post_db[-1]


@app.get('/dog', response_model=List[Dog], summary='Get Dogs')
@cache(expire=30)
def take_dog(kind: DogType):
    return [dog for pk, dog in dogs_db.items() if dog.kind == kind]


@app.post('/dog', response_model=Dog, summary='Create Dog')
def create_dog(dog: Dog):
    pk = dog.pk

    if pk in dogs_db.keys():
        trow_error("The specified PK already exists.", "duplicate")

    dogs_db[pk] = Dog(name=dog.name, pk=pk, kind=dog.kind)
    return dogs_db[pk]


@app.get('/dog/{pk}', response_model=Dog, summary='Get Dog By Pk')
@cache(expire=30)
def take_dog(pk: int):
    dog_dict = {dog.pk: dog for dog in dogs_db.values()}

    if pk not in dog_dict.keys():
        trow_error("Have not dog with this pk.", "not founded")

    return dog_dict.get(pk)


@app.patch('/dog/{pk}', response_model=Dog, summary='Update Dog')
def update_dog(pk: int, dog: Dog):
    dog_dict = {dog.pk: index for index, dog in dogs_db.items()}

    if pk not in dog_dict.keys():
        trow_error("Have not dog with this pk.", "not founded")

    if dog.pk != pk and dog.pk in dog_dict.keys():
        trow_error("The specified PK already exists.", "duplicate")

    index = dog_dict[pk]
    del dogs_db[index]
    dogs_db[index] = Dog(name=dog.name, pk=dog.pk, kind=dog.kind)

    return dogs_db[index]


def trow_error(msg: str, error_type: str):
    raise HTTPException(status_code=422, detail=[{"loc": ["body", "pk"], "msg": msg, "type": error_type}])


redis = aioredis.from_url("redis://localhost")
FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")

if __name__ == '__main__':
    uvicorn.run('main:app', host='localhost', reload=True)
