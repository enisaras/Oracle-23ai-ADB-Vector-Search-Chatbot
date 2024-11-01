from __future__ import print_function
from llama_index.core.llms import ChatMessage
from urllib.request import urlopen
from streamlit_cookies_controller import CookieController
import re as r
import streamlit as st
import json
import uuid
import pickle
import requests
import oracledb
import redis
from redis.cache import CacheConfig

from config import(
    DB_USER,
    DB_PWD,
    DSN,
    CONFIG_DIR,
    WALLET_LOCATION,
    WALLET_PASSWORD,
    STORAGE_TABLE,
    USE_REDIS,
    REDIS_CONN,
)

# Method: CheckForHistory()
# Purpose: This method will determine if the user already has history stored in the
#          database by looking for a stored cookie.
# Returns: str(user_id) | False
def CheckForHistory():
    controller = CookieController()

    user_id = controller.get('vector_db_chat_history')
    if user_id:
        return user_id
    else:
        return False

# Method: StoreChatHistory()
# Purpose: This method will either create a new chat history for a new user, or append
#          the most recent chat history onto a returning user's stored history.
def StoreChatHistory(user_id = None, history = None):
    if not history:
        return

    if USE_REDIS:
        StoreChatHistoryRedis(user_id,history)
    else:
        connection = oracledb.connect(
            user=DB_USER,
            password=DB_PWD,
            config_dir=CONFIG_DIR,
            dsn=DSN,
            wallet_location=WALLET_LOCATION,
            wallet_password=WALLET_PASSWORD
    )
    
        if not user_id:
            random_uuid = str(uuid.uuid4())[:12]
            data = []
            data_user = serialize(history[len(history)-2])
            data_ai = serialize(history[len(history)-1])
            data.append(data_user)
            data.append(data_ai)
    
            controller = CookieController()
            controller.set('vector_db_chat_history',random_uuid)
            pickled_data = pickle.dumps(data)
            cursor = connection.cursor()
            cursor.execute("insert into {} values (:num,:hist)".format(STORAGE_TABLE),[random_uuid,pickled_data])
            connection.commit()
            cursor.close()
        else:
            cursor = connection.cursor()
            cursor.execute("select history from {} where uuid = :num".format(STORAGE_TABLE),[user_id])
    
            row = cursor.fetchone()
            row = row[0].read()
            data = pickle.loads(row)
    
            data_user = serialize(history[len(history)-2])
            data_ai = serialize(history[len(history)-1])
            data.append(data_user)
            data.append(data_ai)
    
            pickled_data = pickle.dumps(data)
            cursor.execute("update {} set history = :hist where uuid = :num".format(STORAGE_TABLE),[pickled_data,user_id])
            connection.commit()
            cursor.close()

    connection.close()

# Method: serialize()
# Purpose: This method takes a ChatMessage object and returns it in a serialized form.
# Returns: dict(new_obj)
def serialize(obj):
    if not isinstance(obj,ChatMessage):
        return
    else:
        new_obj = {
            "role": obj.role,
            "content": obj.content,
            "additional_kwargs": obj.additional_kwargs
        }
        return new_obj

# Method: StoreChatHistoryRedis()
# Purpose: This method allows storing Chat History in Redis, rather than an Oracle DB
def StoreChatHistoryRedis(user_id, history):
    if not history:
        return

    try:
        user_connection = redis.Redis(host=REDIS_CONN['host'], port=REDIS_CONN['port'], protocol=3, cache_config=CacheConfig())
    except ConnectionError as exc:
        raise RuntimeError('Failed to connect to Redis') from exc

    if not user_id:
        random_uuid = str(uuid.uuid4())[:12]
        data = []
        data_user = serialize(history[len(history)-2])
        data_ai = serialize(history[len(history)-1])
        data.append(data_user)
        data.append(data_ai)

        controller = CookieController()
        controller.set('vector_db_chat_history',random_uuid)
        json_data = json.dumps(data)
        user_connection.set(random_uuid,json_data)
    else:
        data = json.loads(user_connection.get(user_id))
        print(data)
        data_user = serialize(history[len(history)-2])
        data_ai = serialize(history[len(history)-1])
        data.append(data_user)
        data.append(data_ai)

        json_data = json.dumps(data)
        user_connection.set(user_id,json_data)
