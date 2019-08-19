#!/usr/bin/python
from beem import Steem
from beem.comment import Comment
from beem.account import Account
from beem.amount import Amount
from beem.blockchain import Blockchain
from beem.nodelist import NodeList
from beem.exceptions import ContentDoesNotExistsException
from beem.utils import addTzInfo, resolve_authorperm, construct_authorperm, derive_permlink, formatTimeString
from datetime import datetime, timedelta, date
from steemengine.wallet import Wallet
from steemengine.tokens import Tokens
import time
import shelve
import json
import logging
import logging.config
import argparse
import os
import sys
from distribubot.utils import print_block_log, check_config, store_data, read_data

logger = logging.getLogger(__name__)


def setup_logging(
    default_path='logging.json',
    default_level=logging.INFO
):
    """Setup logging configuration

    """
    path = default_path
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = json.load(f)
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=default_level)


class Distribubot:
    def __init__(self, config, data_file, steemd_instance):
        self.config = config
        self.data_file = data_file
        self.stm = steemd_instance
        

        self.token_config = {}
        # add log stats
        self.log_data = {"start_time": 0, "last_block_num": None, "new_commands": 0, "stop_block_num": 0,
                         "stop_block_num": 0, "time_for_blocks": 0} 
        config_cnt = 0
        necessary_fields = ["token_account", "symbol", "min_token_in_wallet", "comment_command",
                            "token_memo", "reply", "sucess_reply_body", "fail_reply_body", "no_token_left_body",
                            "user_can_specify_amount", "usage_upvote_percentage", "no_token_left_for_today",
                            "token_in_wallet_for_each_outgoing_token", "maximum_amount_per_comment",
                            "count_only_staked_token"]
        self.token_config = check_config(self.config["config"], necessary_fields, self.stm)

        self.blockchain = Blockchain(mode='head', steem_instance=self.stm)
    

    def run(self, start_block):
        self.stm.wallet.unlock(self.config["wallet_password"])  
        self.blockchain = Blockchain(mode='head', steem_instance=self.stm)
        stop_block = self.blockchain.get_current_block_num()

        if start_block is not None:
            last_block_num = start_block - 1
        self.log_data["start_block_num"] = start_block
        for op in self.blockchain.stream(start=start_block, stop=stop_block, opNames=["comment"],  max_batch_size=50):
            self.log_data = print_block_log(self.log_data, op, self.config["print_log_at_block"])
            last_block_num = op["block_num"]
            
            if op["type"] == "comment":
                token = None
                
                for key in self.token_config:
                    if op["body"].find(self.token_config[key]["comment_command"]) >= 0:
                        token = key
                if token is None:
                    continue
                if op["author"] == self.token_config[token]["token_account"]:
                    continue
                cnt = 0
                c_comment = None
                while c_comment is None and cnt < 5:
                    cnt += 1
                    try:
                        c_comment = Comment(op, steem_instance=self.stm)
                        c_comment.refresh()
                    except:
                        nodelist = NodeList()
                        nodelist.update_nodes()
                        self.stm = Steem(node=nodelist.get_nodes(), num_retries=5, call_num_retries=3, timeout=15)                        
                        time.sleep(1)
                if cnt == 5:
                    logger.warn("Could not read %s/%s" % (op["author"], op["permlink"]))
                    continue
                if c_comment.is_main_post():
                    continue
                if abs((c_comment["created"] - op['timestamp']).total_seconds()) > 9.0:
                    logger.warn("Skip %s, as edited" % c_comment["authorperm"])
                    continue
                already_replied = False
                for r in c_comment.get_all_replies():
                    if r["author"] == self.token_config[token]["token_account"]:
                        already_replied = True
                if already_replied:
                    continue
                
                muting_acc = Account(self.token_config[token]["token_account"], steem_instance=self.stm)
                blocked_accounts = muting_acc.get_mutings()
                if c_comment["author"] in blocked_accounts:
                    logger.info("%s is blocked" % c_comment["author"])
                    continue
                
                # Load bot token balance
                bot_wallet = Wallet(self.token_config[token]["token_account"], steem_instance=self.stm)
                symbol = bot_wallet.get_token(self.token_config[token]["symbol"])

                # parse amount when user_can_specify_amount is true
                amount = self.token_config[token]["default_amount"]
                if self.token_config[token]["user_can_specify_amount"]:
                    start_index = c_comment["body"].find(self.token_config[token]["comment_command"])
                    stop_index = c_comment["body"][start_index:].find("\n")
                    if stop_index >= 0:
                        command = c_comment["body"][start_index + 1:start_index + stop_index]
                    else:
                        command = c_comment["body"][start_index + 1:]
                        
                    command_args = command.replace('  ', ' ').split(" ")[1:]          
                    
                    if len(command_args) > 0:
                        try:
                            amount = float(command_args[0])
                        except Exception as e:
                            exc_type, exc_obj, exc_tb = sys.exc_info()
                            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                            logger.warn("%s - %s - %s" % (str(exc_type), str(fname), str(exc_tb.tb_lineno)))                        
                            logger.info("Could not parse amount")
                    if self.token_config[token]["maximum_amount_per_comment"] and amount > self.token_config[token]["maximum_amount_per_comment"]:
                        amount = self.token_config[token]["maximum_amount_per_comment"]
                
                if not self.config["no_broadcast"] and self.stm.wallet.locked():
                    self.stm.wallet.unlock(self.config["wallet_password"])                
                
                self.log_data["new_commands"] += 1
                wallet = Wallet(c_comment["author"], steem_instance=self.stm)
                token_in_wallet = wallet.get_token(self.token_config[token]["symbol"])
                if token_in_wallet is not None:
                    balance = float(token_in_wallet["balance"])
                    if "stake" in token_in_wallet:
                        balance += float(token_in_wallet['stake']) 
                    if 'delegationsIn' in token_in_wallet and float(token_in_wallet['delegationsIn']) > 0:
                        balance += float(token_in_wallet['delegationsIn'])
                    if 'pendingUnstake' in token_in_wallet and float(token_in_wallet['pendingUnstake']) > 0:
                        balance += float(token_in_wallet['pendingUnstake'])
                    
                    if balance > self.token_config[token]["min_token_in_wallet"]:
                        if self.token_config[token]["token_in_wallet_for_each_outgoing_token"] > 0:
                            max_token_to_give = int(balance / self.token_config[token]["token_in_wallet_for_each_outgoing_token"])
                        else:
                            max_token_to_give = self.token_config[token]["maximum_amount_per_comment"]
                    else:
                        max_token_to_give = 0
                else:
                    max_token_to_give = 0
                
                db_data = read_data(self.data_file)
                if "accounts" in db_data and c_comment["author"] in db_data["accounts"] and token in db_data["accounts"][c_comment["author"]]:
                    if db_data["accounts"][c_comment["author"]][token]["last_date"] == date.today() and self.token_config[token]["token_in_wallet_for_each_outgoing_token"] > 0:
                        max_token_to_give = max_token_to_give - db_data["accounts"][c_comment["author"]][token]["amount"]
                
                if amount > max_token_to_give:
                    amount = max_token_to_give
                if amount > self.token_config[token]["maximum_amount_per_comment"]:
                    amount = self.token_config[token]["maximum_amount_per_comment"]

                if token_in_wallet is None or float(token_in_wallet["balance"]) < self.token_config[token]["min_token_in_wallet"]:
                    reply_body = self.token_config[token]["fail_reply_body"]
                elif max_token_to_give < 1:
                    reply_body = self.token_config[token]["no_token_left_for_today"]
                elif c_comment["parent_author"] == c_comment["author"]:
                    reply_body = "You cannot sent token to yourself."
                elif float(symbol["balance"]) < amount:
                    reply_body = self.token_config[token]["no_token_left_body"]
                else:
                    if "{}" in self.token_config[token]["sucess_reply_body"]:
                        reply_body = (self.token_config[token]["sucess_reply_body"]).format(c_comment["parent_author"])
                    else:
                        reply_body = self.token_config[token]["sucess_reply_body"]
                    if "{}" in self.token_config[token]["token_memo"]:
                        token_memo = (self.token_config[token]["token_memo"]).format(c_comment["author"])
                    else:
                        token_memo = self.token_config[token]["token_memo"]
                        
                    sendwallet = Wallet(self.token_config[token]["token_account"], steem_instance=self.stm)

                    try:
                        logger.info("Sending %.2f %s to %s" % (amount, self.token_config[token]["symbol"], c_comment["parent_author"]))
                        sendwallet.transfer(c_comment["parent_author"], amount, self.token_config[token]["symbol"], token_memo)
                        
                        if "accounts" in db_data:
                            accounts = db_data["accounts"]
                        else:
                            accounts = {}
                        if c_comment["author"] not in accounts:
                            accounts[c_comment["author"]] = {}
                            accounts[c_comment["author"]][token] = {"last_date": date.today(), "n_comments": 1,
                                                                    "amount": amount}
                        elif token not in accounts[c_comment["author"]]:
                            accounts[c_comment["author"]][token] = {"last_date": date.today(), "n_comments": 1,
                                                                    "amount": amount}
                        else:
                            if accounts[c_comment["author"]][token]["last_date"] < date.today():
                                accounts[c_comment["author"]][token] = {"last_date": date.today(), "n_comments": 1,
                                                                        "amount": amount}
                            else:
                                accounts[c_comment["author"]][token]["n_comments"] += 1
                                accounts[c_comment["author"]][token]["amount"] += amount
                            
                        store_data(self.data_file, "accounts", accounts)
                        logger.info("%s - %s" % (c_comment["author"], str(accounts[c_comment["author"]][token])))
                        
                    except Exception as e:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        logger.warn("%s - %s - %s" % (str(exc_type), str(fname), str(exc_tb.tb_lineno)))                     
                        logger.warn("Could not send %s token" % self.token_config[token]["symbol"])
                        continue
                        
                reply_identifier = construct_authorperm(c_comment["parent_author"], c_comment["parent_permlink"])
                if self.config["no_broadcast"]:
                    logger.info("%s" % reply_body)
                else:
                    try:
                        self.stm.post("", reply_body, author=self.token_config[token]["token_account"], reply_identifier=reply_identifier)
                    except Exception as e:
                        exc_type, exc_obj, exc_tb = sys.exc_info()
                        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                        logger.warn("%s - %s - %s" % (str(exc_type), str(fname), str(exc_tb.tb_lineno)))                     
                        logger.warn("Could not reply to post")
                        continue
                    if self.token_config[token]["usage_upvote_percentage"] > 0:
                        try:
                            c_comment.upvote(self.token_config[token]["usage_upvote_percentage"], voter=self.token_config[token]["token_account"])
                        except Exception as e:
                            exc_type, exc_obj, exc_tb = sys.exc_info()
                            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
                            logger.warn("%s - %s - %s" % (str(exc_type), str(fname), str(exc_tb.tb_lineno)))                        
                            logger.warn("Could not upvote comment")
                            
                time.sleep(4)
        return last_block_num


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config", help="Config file in JSON format")
    parser.add_argument("--logconfig", help="Logger Config file in JSON format", default='logger.json')
    parser.add_argument("--datadir", help="Data storage dir", default='.')
    args = parser.parse_args()
    
    setup_logging(default_path=args.logconfig)
    
    logger.info("Loading config: %s" % str(args.config))
    config = json.loads(open(args.config).read())
    datadir = args.datadir

    nodelist = NodeList()
    nodelist.update_nodes()
    stm = Steem(node=nodelist.get_nodes(), num_retries=5, call_num_retries=3, timeout=15)
    data_file = os.path.join(datadir, 'data.db')
    bot = Distribubot(
        config,
        data_file,
        stm
    )
    
    data_file = os.path.join(datadir, 'data.db')
    data_db = read_data(data_file)
    if "last_block_num" in data_db:
        last_block_num = data_db["last_block_num"]
    else:
        last_block_num = 0
    if "comment_queue" in data_db:
        comment_queue = data_db["comment_queue"]
    else:
        comment_queue = {}
  
    if "last_block_num" in data_db:
        start_block = data_db["last_block_num"] + 1
    else:
        start_block = None
    logger.info("starting token distributor..")
    block_counter = None
    while True:
        
        last_block_num = bot.run(start_block)
        # Update nodes once a day
        if block_counter is None:
            block_counter = last_block_num
        elif last_block_num - block_counter > 20 * 60 * 24:
            nodelist.update_nodes()
            stm = Steem(node=nodelist.get_nodes(), num_retries=5, call_num_retries=3, timeout=15)
            
            bot.stm = stm

        start_block = last_block_num + 1
        store_data(data_file, "last_block_num", last_block_num)
        time.sleep(3)

    
if __name__ == "__main__":
    main()
