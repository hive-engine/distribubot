#!/usr/bin/python
from beem import Steem
from beem.comment import Comment
from beem.account import Account
from beem.amount import Amount
from beem.blockchain import Blockchain
from beem.nodelist import NodeList
from beem.exceptions import ContentDoesNotExistsException
from beem.utils import addTzInfo, resolve_authorperm, construct_authorperm, derive_permlink, formatTimeString
from datetime import datetime, timedelta
from steemengine.wallet import Wallet
from steemengine.tokens import Tokens
import time
import shelve
import json
import logging
import argparse
import os
import sys

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig()


def print_block_log(log_data, op, print_log_at_block=200):
    # Use variables for all dict elements for better code readability
    start_time = log_data["start_time"]
    last_block_num = log_data["last_block_num"]
    if "new_commands" in log_data:
        new_commands = log_data["new_commands"]
    else:
        new_commands = None
        
    start_block_num = log_data["start_block_num"]
    stop_block_num = log_data["stop_block_num"]
    time_for_blocks = log_data["time_for_blocks"]
    
    if last_block_num is None:
        start_time = time.time()
        last_block_num = op["block_num"]
        if new_commands is not None:
            new_commands = 0
    if (op["block_num"] - last_block_num) > print_log_at_block:
        time_for_blocks = time.time() - start_time
        logger.info("---------------------")
        # print extended log when block log difference is greater than 200
        if print_log_at_block > 200 and (stop_block_num - start_block_num) > 0:
            percentage_done = (op["block_num"] - start_block_num) / (stop_block_num - start_block_num) * 100
            logger.info("Block %d -- Datetime %s -- %.2f %% finished" % (op["block_num"], op["timestamp"], percentage_done))
            running_hours = (stop_block_num - op["block_num"]) * time_for_blocks / print_log_at_block / 60 / 60
            logger.info("Duration for %d blocks: %.2f s (%.3f s per block) -- %.2f hours to go" % (print_log_at_block, time_for_blocks, time_for_blocks / print_log_at_block, running_hours))
        else:
            logger.info("Block %d -- Datetime %s" % (op["block_num"], op["timestamp"]))
        if new_commands is not None:
            logger.info("%d  new scot commands" % new_commands)
            new_commands = 0
        start_time = time.time()
        
        last_block_num = op["block_num"]
    log_data["start_time"] = start_time
    log_data["last_block_num"] = last_block_num
    if new_commands is not None:
        log_data["new_commands"] = new_commands
    log_data["time_for_blocks"] = time_for_blocks
    return log_data


def check_config(config, necessary_fields, stm):
    config_cnt = 0
    token_config = {}
    token_list = Tokens()
    for conf in config:
        config_cnt += 1
        # check if all fields are set
        all_fields_ok = True
        for field in necessary_fields:
            if field not in conf:
                logger.warn("Error in %d. config: %s missing" % (config_cnt, field))
                all_fields_ok = False
        if not all_fields_ok:
            continue
        # Check if token_account exists (exception will be raised when not)
        Account(conf["token_account"], steem_instance=stm)
        # Check if symbol exists
        if token_list.get_token(conf["symbol"]) is None:
            logger.warn("Token %s does not exists" % conf["symbol"])
            continue
        scot_wallet = Wallet(conf["token_account"], steem_instance=stm)
        symbol = scot_wallet.get_token(conf["symbol"])
        logger.info("%s has %s token" % (conf["token_account"], str(symbol)))
        token_config[conf["symbol"]] = conf
    if len(token_config) == 0:
        raise Exception("Broken config, shutdown bot...")
    logger.info("%d configs were found." % len(token_config))
    
    return token_config

def store_data(data_file, parameter, value):
    data_db = shelve.open(data_file)
    data_db[parameter] = value
    data_db.close()

def read_data(data_file):
    data = {}
    data_db = shelve.open(data_file)
    for key in data_db:
        data[key] = data_db[key]
    data_db.close()
    return data