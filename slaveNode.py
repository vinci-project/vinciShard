from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QMutex
from PyQt5.QtCore import QTimer
from PyQt5.QtCore import QThread

from vncCrypto import VncCrypto
from vncCrypto.mrkl import VncTree
from vncCrypto.signChecker import SignChecker

from netTools import NetEngine
from jsonMaker import JsonPackets

from datetime import datetime, date, time
import json, sys, os, redis, pymongo, math
from pymongo import MongoClient

class slaveWorker(QThread):
    floodPacket = pyqtSignal(str, str, int)
    sendPacket = pyqtSignal(str, str, int)
    setPurifyList = pyqtSignal(list)

    def __init__(self, myAddress: str, privateKey: str):
        super().__init__()
        self.cryptor = VncCrypto()
        self.transactionMemory = set()
        self.precommitedBlockHash = None
        self.signatureMemory = []
        self.transactionsInPBlock = set()
        self.stemAddress = None
        self.stemPublicKey = "0320ab99dee836df538e5e09a7c692c0aef02d91a11ce711992b95835f28243242"
        self.nodesCount = 0
        self.myAddress = myAddress
        self.packetStack = list()
        self.priorPacketStack = list()
        self.stackMutex = QMutex()
        self.signChecker = SignChecker()
        self.version = "0.1.0"
        self.redis_host = os.getenv("REDIS_PORT_6379_TCP_ADDR") or 'localhost'
        self.redis_port = os.getenv("REDIS_PORT_6379_TCP_PORT") or '6379'
        self.mongo_host = os.getenv("MONGO_PORT_27017_TCP_ADDR") or 'localhost'
        self.mongo_port = 27017
        self.mongo_conn = MongoClient(self.mongo_host, self.mongo_port)
        self.redis = redis.StrictRedis(self.redis_host, self.redis_port, db=1)
        self.mongo = self.mongo_conn.vncsphere
        self.mongo_conn.drop_database(self.mongo) # CLEAR MONGODB VNCSPHERE DATABASE

        self.lastCheckBlockBalance = 0
        self.currentTokenTypes = ["VINCI"]
        self.blockReward = 10
        self.blocks_in_genesis = 10000000
        self.timeToGarbageCollector = 300*1000 #5 minutes
        self.MAX_TRAN_COUNT_IN_BLOCK = 9000
        self.MAX_TRAN_FOR_USER_IN_BLOCK = 9000
        self.tempMoneySum = 0
        self.updateBalanceStep = 1000
        #----------------------------------------- TOKENOMIKS BASIC
        self.voteFeeArray = {"VT": 10, "UFT": 100, "DFT": 100}
        self.allTokens = 23*1000*1000 #23 mln tokens
        self.tokensToReward = self.allTokens * 0.26 #reward tokens for 4 years
        #self.freezeToAT = 16*1000
        self.freezeToAT = 16
        self.freezeToVT = 1
        self.fee = 0
        self.freeZoneHeight = 12*60*24*365*4
        #self.freeZoneHeight = 10

        #-----------------------------------------
        #self.cryptor.generateKeys()
        print("PRIVATE KEY!", privateKey)
        self.cryptor.setPrivateKey(privateKey)
        print("PUBLIC KEY!", self.cryptor.getPublicKey())
        self.redis.flushdb()
        print(self.redis.set("VERSION", self.version))

        ##################### TEST
        #self.redis.zadd("BALANCE:VINCI",10000, "0323f264fd64a684db1e36a2c97b58867e0625f797008206216576fea2114bdbca")
        #self.redis.zadd("BALANCE:NBL",10000, "027426df275f98bb0f66bb4f1a92352296be233b115415f709540e8caa80d820f2")
        #self.redis.zadd("RAW TRANSACTIONS", 1541777858, '{"TT":"ET","SENDER":"0323f264fd64a684db1e36a2c97b58867e0625f797008206216576fea2114bdbca","RECEIVER":"027426df275f98bb0f66bb4f1a92352296be233b115415f709540e8caa80d820f2","STT":"VINCI","STC":"100","RTT":"NBL","RTC":"10","TST":"1541777858","SIGNATURE":"3b229fe53c21b472e82d4eec2a9bbde9c340c243b80fbd7ee1897b065708603352df740f1493d4d7215802065be5fde34fd8e0cae65afa11b5d69dc0cfd0a01a00"}')

    @staticmethod
    def isfloat(value):
        try:
            float(value)
            return True
        except:
            return False

    @pyqtSlot(str, str)
    def appendPacketToStack(self, address: str, packet: str):
        # if not self.signChecker.checkTran(packet):
        #     return
        jpacket = json.loads(packet)
        packetType = jpacket["TT"]

        self.stackMutex.lock()
        if packetType == "SG" or packetType == "CT" or packetType == "BL" or packetType == "PURIFIER":
            self.packetStack.insert(0, (address, packet))
        else:
            self.packetStack.append((address, packet))
        self.stackMutex.unlock()

    def getAnyFee(self, token_type):
        if token_type == "VINCI":
            return self.fee
        else:
            return 0

    def getAnyVoteFee(self, voteType):
        if self.voteFeeArray.get(voteType) is None:
            return 0
        else:
            return self.voteFeeArray.get(voteType)


    def handler(self, address: str, packet: str):
        jpacket = json.loads(packet)

        print("RECIVE PACKET: ", jpacket["TT"])

        if jpacket["TT"] == "SG":
            if self.precommitedBlockHash == jpacket.get("HASH"):
                self.signatureMemory.append(jpacket.get("SIGNPB"))
            else:
                print("Recive old block SG - failed and return")
                return

            signNeedCount = len(set(self.signatureMemory))
            if signNeedCount >= int((2 / 3) * self.nodesCount):

                # CLEAR TRAN LIST #
                self.transactionMemory = self.transactionMemory - set(self.transactionsInPBlock)
                # CLEAR TRAN LIST #

                self.cttime = 0
                print(self.signatureMemory)
                self.sendPacket.emit(self.stemAddress, JsonPackets.createCommitBlock(self.cryptor, self.precommitedBlock, self.signatureMemory), 1)
                self.transactionsInPBlock.clear()
                self.signatureMemory.clear()
            return

        if jpacket["TT"] == "CBRH":
                print("CBRH KEEP!")
                if jpacket["SENDER"] == self.stemPublicKey: #IF SENDER IS MASTER NODE
                    hash = jpacket["HASH"]

                    JTPCB = json.loads(self.precommitedBlock)
                    JTPCB.pop("SIGNATURE")

                    if VncTree.hash(json.dumps(JTPCB, separators=(',', ':'))) != hash:
                        print("BAD HASH!!! FROM CBRH:", VncTree.hash(self.precommitedBlock), "AND", hash)
                        # GIVE ME ALL SIZE BLOCK!
                        self.sendPacket.emit(self.stemAddress, JsonPackets.giveAllSizeBlock(self.cryptor, jpacket["BHEIGHT"]), 1)
                        return

                    block = json.loads(self.precommitedBlock)
                    block.update({"STEM_SIGNATURE": jpacket["STEM_SIGNATURE"]})
                    block.update({"NODE_SIGNATURES": jpacket["SIGNS"]})

                    self.mongo.vncchain.save(block)
                    #self.redis.zadd("VNCCHAIN", block["BHEIGHT"], json.dumps(block, separators=(',', ':')))


                    self.precommitedBlock = "" # CLEAR MEMMORY AFTER SAVE BLOCK IN CHAIN
                    self.checkBalance()

                    # # DELETE AFTER ENDING MAIN BLOCKCHAIN EXPLORER
                    # money = self.redis.zscore("MONEY MOVE", datetime.now().strftime("%Y-%m-%d"))
                    #
                    # if money is None:
                    #     money = 0
                    # else:
                    #     if slaveWorker.isfloat(money):
                    #         money = float(money)
                    #     else:
                    #         print("CLEAR MONEY BUF-BUF")
                    #         money = 0
                    # # DELETE AFTER ENDING MAIN BLOCKCHAIN EXPLORER

                    for tran in block["TRANSACTIONS"]:

                        stran = json.dumps(tran, separators=(',', ':'))
                        print("ZREEEEEEEM:", stran, self.redis.zrem("RAW TRANSACTIONS", stran))
                        self.redis.zrem("RAW TRANSACTIONS", stran)

                        if tran["TT"] == "ET":
                            sender = tran["SENDER"]
                            receiver = tran["RECEIVER"]
                            sign = tran["SIGNATURE"]
                            self.redis.zadd("COMPLETE TRANSACTIONS", int(block["BHEIGHT"]), VncTree.hash(sign))
                            self.redis.set("TRANSACTIONS:" + VncTree.hash(sign), stran)

                        if tran["TT"] == "ST":
                            sender = tran["SENDER"]
                            receiver = tran["RECEIVER"]
                            sign = tran["SIGNATURE"]
                            self.redis.zadd("COMPLETE TRANSACTIONS", int(block["BHEIGHT"]), VncTree.hash(sign))
                            self.redis.set("TRANSACTIONS:" + VncTree.hash(sign), stran)

                        if tran["TT"] == "AT":
                            sender = tran["SENDER"]
                            sign = tran["SIGNATURE"]
                            self.redis.zadd("COMPLETE TRANSACTIONS", int(block["BHEIGHT"]), VncTree.hash(sign))
                            self.redis.zadd("APPLICANTS", int(block["BHEIGHT"]), sender)
                            self.redis.set("TRANSACTIONS:" + VncTree.hash(sign), stran)

                        if tran["TT"] == "UAT":
                            sender = tran["SENDER"]
                            sign = tran["SIGNATURE"]
                            self.redis.zadd("COMPLETE TRANSACTIONS", int(block["BHEIGHT"]), VncTree.hash(sign))
                            self.redis.zrem("APPLICANTS", sender)
                            self.redis.set("TRANSACTIONS:" + VncTree.hash(sign), stran)

                        if tran["TT"] == "VT":
                            sender = tran["SENDER"]
                            receiver = tran["RECEIVER"]
                            votes = int(tran["VOTES"])

                            sign = tran["SIGNATURE"]
                            self.redis.zadd("COMPLETE TRANSACTIONS", int(block["BHEIGHT"]), VncTree.hash(sign))
                            self.redis.set("TRANSACTIONS:" + VncTree.hash(sign), stran)

                            tempVotes = self.redis.zscore("VOTES:" + sender, receiver)
                            if tempVotes == None:
                                tempVotes = 0
                            self.redis.zadd("VOTES:" + receiver, tempVotes + votes, sender)

                            tempUntVotes = self.redis.zscore("UNTVOTES", sender)
                            if tempUntVotes == None:
                                tempUntVotes = 0
                            self.redis.zadd("UNTVOTES", tempUntVotes + votes, sender)

                        if tran["TT"] == "UFT": #UPFEETRAN
                            sender = tran["SENDER"]
                            receiver = tran["RECEIVER"]
                            votes = int(tran["VOTES"])

                            sign = tran["SIGNATURE"]
                            self.redis.zadd("COMPLETE TRANSACTIONS", int(block["BHEIGHT"]), VncTree.hash(sign))
                            self.redis.set("TRANSACTIONS:" + VncTree.hash(sign), stran)

                            tempVotes = self.redis.zscore("UFT-VOTES:" + sender, receiver)
                            if tempVotes == None:
                                tempVotes = 0
                            self.redis.zadd("UFT-VOTES:" + sender, tempVotes + votes, receiver)

                            tempUntVotes = self.redis.zscore("UFT-UNTVOTES", sender)
                            if tempUntVotes == None:
                                tempUntVotes = 0
                            self.redis.zadd("UFT-UNTVOTES", tempUntVotes + votes, sender)

                        if tran["TT"] == "DFT": #DOWNFEETRAN
                            sender = tran["SENDER"]
                            receiver = tran["RECEIVER"]
                            votes = int(tran["VOTES"])

                            sign = tran["SIGNATURE"]
                            self.redis.zadd("COMPLETE TRANSACTIONS", int(block["BHEIGHT"]), VncTree.hash(sign))
                            self.redis.set("TRANSACTIONS:" + VncTree.hash(sign), stran)

                            tempVotes = self.redis.zscore("DFT-VOTES:" + sender, receiver)
                            if tempVotes == None:
                                tempVotes = 0
                            self.redis.zadd("DFT-VOTES:" + sender, tempVotes + votes, receiver)

                            tempUntVotes = self.redis.zscore("DFT-UNTVOTES", sender)
                            if tempUntVotes == None:
                                tempUntVotes = 0
                            self.redis.zadd("DFT-UNTVOTES", tempUntVotes + votes, sender)

                        if tran["TT"] == "UVT":
                            sender = tran["SENDER"]
                            receiver = tran["RECEIVER"]
                            sign = tran["SIGNATURE"]

                            self.redis.zadd("COMPLETE TRANSACTIONS", int(block["BHEIGHT"]), VncTree.hash(sign))
                            self.redis.zrem("VOTES:" + sender, receiver)
                            self.redis.set("TRANSACTIONS:" + VncTree.hash(sign), stran)

                    #self.redis.zadd("MONEY MOVE", money, datetime.now().strftime("%Y-%m-%d"))

        if jpacket["TT"] == "CBR":
                print("CBR KEEP!")
                if jpacket["SENDER"] == self.stemPublicKey: #IF SENDER IS MASTER NODE
                    block = jpacket["BLOCK"]
                    block.update({"STEM_SIGNATURE": jpacket["SIGNATURE"]})
                    self.mongo.vncchain.save(block)
                    #self.redis.zadd("VNCCHAIN", block["BHEIGHT"], json.dumps(block, separators=(',', ':')))
                    self.checkBalance()

                    for tran in block["TRANSACTIONS"]:

                        self.redis.zrem("RAW TRANSACTIONS", json.dumps(tran, separators=(',', ':')))

                        if tran["TT"] == "ST":
                            sender = tran["SENDER"]
                            receiver = tran["RECEIVER"]
                            sign = tran["SIGNATURE"]
                            #money += float(tran["CTOKEN"])
                            self.redis.zadd("COMPLETE TRANSACTIONS", int(block["BHEIGHT"]), str(sender) + str(receiver) + str(sign))

                        if tran["TT"] == "AT":
                            sender = tran["SENDER"]
                            self.redis.zadd("APPLICANTS", int(block["BHEIGHT"]), sender)

                        if tran["TT"] == "UAT":
                            sender = tran["SENDER"]
                            self.redis.zrem("APPLICANTS", sender)

                        if tran["TT"] == "VT":
                            sender = tran["SENDER"]
                            receiver = tran["RECEIVER"]
                            votes = tran["VOTES"]
                            self.redis.zadd("VOTES:" + sender, votes, receiver)

                            temp_votes = self.redis.zscore("UNTVOTES", sender)
                            if temp_votes is None:
                                temp_votes = 0

                            self.redis.zadd("UNTVOTES", temp_votes + votes, sender)

                        if tran["TT"] == "UVT":
                            sender = tran["SENDER"]
                            receiver = tran["RECEIVER"]
                            self.redis.zrem("VOTES:" + sender, receiver)

                            del_votes = self.redis.zscore("VOTES:" + sender, receiver)
                            if del_votes is None:
                                del_votes = 0
                            self.redis.zrem("VOTES:" + sender, receiver)

                            temp_votes = self.redis.zscore("UNTVOTES", sender)
                            if temp_votes is None:
                                temp_votes = 0
                            self.redis.zadd("UNTVOTES", temp_votes - del_votes, sender)


                        #self.redis.zadd("MONEY MOVE", money, datetime.now().strftime("%Y-%m-%d"))

            # IF BLOCK FROM STEM NODE

        if jpacket["TT"] == "BL":
            # IF NEED SIGNATURE WORK
            transactions = jpacket["TRANSACTIONS"]
            trans = []
            for tran in transactions:
                trans.append(json.dumps(tran, separators=(',', ':')))

            unionTran = set(trans) - self.transactionMemory
            okSign = True

            if len(unionTran) != 0:  # Build block with another transactions
                for newTran in unionTran:
                    jnewTran = json.loads(newTran)
                    signature = jnewTran.pop("SIGNATURE")
                    sender = jnewTran.get("SENDER")
                    if not self.cryptor.verifyMessage(signature, sender, json.dumps(jpacket, separators=(',', ':'))):
                        self.sendPacket.emit(address, JsonPackets.createСomplaint(self.cryptor, packet, newTran), 1)
                        okSign = False

            if okSign:  # Good block!
                precommitedBlock = json.dumps(jpacket, separators=(',', ':'))
                self.sendPacket.emit(address,JsonPackets.createSignaturePrecommitedBlock(self.cryptor, precommitedBlock, VncTree.hash(precommitedBlock)), 1)

            return

        if jpacket["TT"] == "CT":

            self.updateFee()
            print("RECEIVE PACKET:", packet)

            #blockchain_height = self.redis.zcard("VNCCHAIN")

            blockchain_height = self.mongo.vncchain.find().count()
            # pymongo_cursor = self.mongo.vncchain.find().sort("BHEIGHT", pymongo.ASCENDING).limit(1)
            # blockchain_height = dict(pymongo_cursor).get("BHEIGHT")

            if blockchain_height is None:
                blockchain_height = 0

            if blockchain_height != jpacket["NBH"]:
                print("NBH not Supported in my version BlockChain!")
                #print(blockchain_height, jpacket["NBH"])
                self.sendPacket.emit(self.stemAddress, JsonPackets.badAnswer(self.cryptor), 1)
                return False

            txmas = []
            txcount = self.redis.zcard("RAW TRANSACTIONS")
            if txcount < self.MAX_TRAN_COUNT_IN_BLOCK:
                txmas = self.redis.zrange("RAW TRANSACTIONS", 0, -1)
            else:
                txmas = self.redis.zrange("RAW TRANSACTIONS", 0, self.MAX_TRAN_COUNT_IN_BLOCK)

            tranUserCount = {}
            tempBalanceMemmory = {}
            tempDictBalanceMemmory = {}

            decodeTxmas = []

            print("TXMAS_LEN:", len(txmas))

            for tran in txmas:
                try:
                    jtran = json.loads(tran)
                except Exception:
                    print("000. GO TO HELL!", tran)
                    continue

                tokenPrefix = "VINCI"

                if jtran["TT"] == "ET":
                    print("STEP 1")
                    sender = jtran["SENDER"]  # money sender
                    receiver = jtran["RECEIVER"]  # money receiver

                    stt = jtran["STT"]  # money sender token type
                    rtt = jtran["RTT"]  # money receiver token type
                    stc = jtran["STC"]  # money sender token count
                    rtc = jtran["RTC"]  # money receiver token count

                    # if jtran.get("INIT_SIGNATURE") is not None:
                    #     init_sign = jtran.pop("INIT_SIGNATURE")
                    # else:
                    #     init_sign = None
                    #
                    # sign = jtran.pop("SIGNATURE")
                    #
                    # if self.cryptor.verifyMessage(sign, sender, json.dumps(tran, separators=(',', ':'))):
                    #     tempBalance = tempBalanceMemmory.get(currentSender)

                    # CHECK DOUBLE MONEY SEND
                    tempSBalanceMemmory = tempDictBalanceMemmory.get(stt)
                    if tempSBalanceMemmory is None:
                        tempSBalanceMemmory = {}
                        tempSBalance = self.redis.zscore("BALANCE:" + stt, sender)
                    else:
                        tempSBalance = tempSBalanceMemmory.get(sender)
                        if tempSBalance is None:
                            tempSBalance = self.redis.zscore("BALANCE:" + stt, sender)

                    tempRBalanceMemmory = tempDictBalanceMemmory.get(rtt)
                    if tempRBalanceMemmory is None:
                        tempRBalanceMemmory = {}
                        tempRBalance = self.redis.zscore("BALANCE:" + rtt, receiver)
                    else:
                        tempRBalance = tempRBalanceMemmory.get(currentSender)
                        if tempRBalance is None:
                            tempRBalance = self.redis.zscore("BALANCE:" + rtt, receiver)

                    if tempSBalance is None:
                        print("1. GO TO HELL ET!")
                        self.redis.zadd("FAILED TRANSACTIONS", 1, VncTree.hash(jtran["SIGNATURE"]))
                        self.redis.zrem("RAW TRANSACTIONS", tran)
                        continue

                    if tempRBalance is None:
                        print("1. GO TO HELL ET!")
                        self.redis.zadd("FAILED TRANSACTIONS", 1, VncTree.hash(jtran["SIGNATURE"]))
                        self.redis.zrem("RAW TRANSACTIONS", tran)
                        continue

                    if stt == "VINCI":
                        totalSBalance = tempSBalance - self.getFreezeTokens(sender)
                    else:
                        totalSBalance = tempSBalance

                    if totalSBalance < (float(stc) + self.getAnyFee(stt)):
                        self.redis.zrem("RAW TRANSACTIONS", tran)
                        self.redis.zadd("FAILED TRANSACTIONS", 2, VncTree.hash(jtran["SIGNATURE"]))
                        print("2. GO TO HELL ET!")
                        continue
                    else:
                        tempSBalance = tempSBalance - (float(stc) + self.getAnyFee(stt))

                    if stt == "VINCI":
                        totalRBalance = tempRBalance - self.getFreezeTokens(receiver)
                    else:
                        totalRBalance = tempRBalance

                    if totalRBalance < (float(stc) + self.getAnyFee(rtt)):
                        self.redis.zrem("RAW TRANSACTIONS", tran)
                        self.redis.zadd("FAILED TRANSACTIONS", 2, VncTree.hash(jtran["SIGNATURE"]))
                        print("2. GO TO HELL ET!")
                        continue
                    else:
                        tempRBalance = tempRBalance - (float(rtc) + self.getAnyFee(rtt))

                    tempSBalanceMemmory.update({sender: tempSBalance})
                    tempRBalanceMemmory.update({receiver: tempRBalance})
                    tempDictBalanceMemmory.update({stt: tempSBalanceMemmory})
                    tempDictBalanceMemmory.update({rtt: tempRBalanceMemmory})

                    decodeTxmas.append(tran)

                if jtran["TT"] == "AT":
                    currentSender = jtran["SENDER"]

                    # CHECK DOUBLE MONEY SEND
                    tempBalanceMemmory = tempDictBalanceMemmory.get("VINCI")
                    if tempBalanceMemmory is None:
                        tempBalanceMemmory = {}
                        tempBalance = self.redis.zscore("BALANCE:VINCI", currentSender)
                    else:
                        tempBalance = tempBalanceMemmory.get(currentSender)
                        if tempBalance is None:
                            tempBalance = self.redis.zscore("BALANCE:VINCI", currentSender)

                    if tempBalance is None:
                        print("1. GO TO HELL AT!")
                        self.redis.zadd("FAILED TRANSACTIONS", 1, VncTree.hash(jtran["SIGNATURE"]))
                        self.redis.zrem("RAW TRANSACTIONS", tran)
                        continue

                    if (tempBalance - self.getFreezeTokens(currentSender)) < self.freezeToAT:
                        self.redis.zrem("RAW TRANSACTIONS", tran)
                        self.redis.zadd("FAILED TRANSACTIONS", 2, VncTree.hash(jtran["SIGNATURE"]))
                        print("2. GO TO HELL AT!")
                        continue
                    else:
                        tempBalance = tempBalance - self.freezeToAT

                    tempBalanceMemmory.update({currentSender: tempBalance})
                    tempDictBalanceMemmory.update({"VINCI": tempBalanceMemmory})
                    decodeTxmas.append(tran)

                if jtran["TT"] == "VT" or jtran["TT"] == "UFT" or jtran["TT"] == "DFT": # VOTE, UPFEE, DOWNFEE
                    currentSender = jtran["SENDER"]

                    # CHECK DOUBLE MONEY SEND
                    tempBalanceMemmory = tempDictBalanceMemmory.get("VINCI")
                    if tempBalanceMemmory is None:
                        tempBalanceMemmory = {}
                        tempBalance = self.redis.zscore("BALANCE:VINCI", currentSender)
                    else:
                        tempBalance = tempBalanceMemmory.get(currentSender)
                        if tempBalance is None:
                            tempBalance = self.redis.zscore("BALANCE:VINCI", currentSender)

                    if tempBalance is None:
                        print("1. GO TO HELL VT!")
                        self.redis.zadd("FAILED TRANSACTIONS", 1, VncTree.hash(jtran["SIGNATURE"]))
                        self.redis.zrem("RAW TRANSACTIONS", tran)
                        continue

                    if (tempBalance - self.getFreezeTokens(currentSender)) < self.freezeToVT*int(jtran["VOTES"]):
                        self.redis.zrem("RAW TRANSACTIONS", tran)
                        self.redis.zadd("FAILED TRANSACTIONS", 2, VncTree.hash(jtran["SIGNATURE"]))
                        print("2. GO TO HELL VT!")
                        continue
                    else:
                        if jtran["TT"] == "VT":
                            tempBalance = tempBalance - self.getAnyVoteFee(jtran["TT"])*int(jtran["VOTES"])
                        if jtran["TT"] == "UFT":
                            tempBalance = tempBalance - self.getAnyVoteFee(jtran["TT"])*int(jtran["VOTES"])
                        if jtran["TT"] == "DFT":
                            tempBalance = tempBalance - self.getAnyVoteFee(jtran["TT"])*int(jtran["VOTES"])

                    tempBalanceMemmory.update({currentSender: tempBalance})
                    tempDictBalanceMemmory.update({"VINCI": tempBalanceMemmory})
                    decodeTxmas.append(tran)

                if jtran["TT"] == "ST":
                    currentSender = jtran["SENDER"]
                    # CHECK 3 TRAN FROM ONE USER
                    count = tranUserCount.get(currentSender)
                    if count is None:
                        tranUserCount.update({currentSender:1})
                    else:
                        if count >= self.MAX_TRAN_FOR_USER_IN_BLOCK:
                           continue
                        else:
                            tranUserCount.update({currentSender:(count + 1)})

                    # CHECK DOUBLE MONEY SEND
                    tempBalanceMemmory = tempDictBalanceMemmory.get(jtran["TTOKEN"])
                    if tempBalanceMemmory is None:
                        tempBalanceMemmory = {}
                        tempBalance = self.redis.zscore("BALANCE:" + jtran["TTOKEN"], currentSender)
                    else:
                        tempBalance = tempBalanceMemmory.get(currentSender)
                        if tempBalance is None:
                            tempBalance = self.redis.zscore("BALANCE:" + jtran["TTOKEN"], currentSender)

                    if tempBalance is None:
                        print("1. GO TO HELL!")
                        self.redis.zadd("FAILED TRANSACTIONS", 1, VncTree.hash(jtran["SIGNATURE"]))
                        self.redis.zrem("RAW TRANSACTIONS", tran)
                        continue

                    if (tempBalance - self.getFreezeTokens(currentSender)) < (float(jtran["CTOKEN"]) + self.fee):
                        self.redis.zrem("RAW TRANSACTIONS", tran)
                        self.redis.zadd("FAILED TRANSACTIONS", 2, VncTree.hash(jtran["SIGNATURE"]))
                        print("2. GO TO HELL!")
                        continue
                    else:
                        tempBalance = tempBalance - (float(jtran["CTOKEN"]) + self.fee)

                    tempBalanceMemmory.update({currentSender: tempBalance})
                    tempDictBalanceMemmory.update({jtran["TTOKEN"]: tempBalanceMemmory})
                    decodeTxmas.append(tran)


            self.transactionsInPBlock = decodeTxmas
            precommitBlock = JsonPackets.createPrecommitBlock(self.cryptor, self.version, self.transactionsInPBlock, blockchain_height, self.fee)

            # CLEAR ZONE #
            self.signatureMemory.clear()
            # CLEAR ZONE #

            self.precommitedBlock = precommitBlock
            self.precommitedBlockHash = VncTree.hash(precommitBlock)
            signature = json.loads(precommitBlock).get("SIGNATURE")
            print("APPEND MY SIGNATURE!", signature)
            self.signatureMemory.append(signature)

            signNeedCount = len(set(self.signatureMemory))

            if signNeedCount >= math.ceil((2 / 3) * self.nodesCount): # !!!ONLY WORK IN TESTNET WITH ONE NODE!!!
                print("SIGN COMPLETE")
                #self.transactionMemory = self.transactionMemory - self.transactionsInPBlock  # ДОБАВИТЬ ПОИСК И УДАЛЕНИЕ
                # CLEAR TRAN LIST #

                self.sendPacket.emit(self.stemAddress, JsonPackets.createCommitBlock(self.cryptor, self.precommitedBlock, self.signatureMemory), 1)

                self.transactionsInPBlock.clear()
                self.signatureMemory.clear()
            else:
                print("SIGN NOT COMPLETE")
                #print ("ZONE 2")
                self.floodPacket.emit(precommitBlock, str(), 1)
            return

        if jpacket["TT"] == "PURIFIER":
            #print("RECEIVE PACKET:", packet)
            self.updateFee()
            self.stemAddress = address

            pymongo_cursor = self.mongo.vncchain.find().sort("BHEIGHT", pymongo.ASCENDING).limit(1)
            blockchain_height = dict(pymongo_cursor).get("BHEIGHT")

            if blockchain_height is None:
                blockchain_height = 0

            #blockchain_height = self.redis.zcard("VNCCHAIN")

            tempList = jpacket["CLEAN_LIST"]
            tempKeyList = jpacket["CLEAN_KEY_LIST"]
            if len(tempList) != len(tempKeyList):
                print("BAD PURIFIER BLOCK! STOP WORK!")
                return

            if blockchain_height == 0 or blockchain_height % self.blocks_in_genesis == 0:
                self.mongo.vncchain.save(jpacket)
                #self.redis.zadd("VNCCHAIN", jpacket["BHEIGHT"], json.dumps(jpacket, separators=(',', ':')))

            NLIST = []
            for temp in zip(tempList, tempKeyList):
                NLIST.append({"ADDRESS": temp[0], "TYPE": "1", "PUBLICKEY": temp[1]})

            self.redis.set("NODES LIST", json.dumps({"NLIST": NLIST}, separators=(',', ':')))

            self.nodesCount = len(tempList)
            self.setPurifyList.emit(tempList)
            return

        # if jpacket["TT"] == "BT":
        #     #print("RECEIVE BT")
        #     result = self.benchmark.benchmarkStart(jpacket["START"])
        #     packet = JsonPackets.myBenchmarkResult(self.cryptor, result, jpacket["START"])
        #     #print("SEND MBR")
        #     self.sendPacket.emit(address, packet, 1)
        #     return

        # if jpacket["TT"] == "AT":
        #     print("RECEIVE PACKET:", packet)
        #     self.transactionMemory.add(packet)
        #     self.floodPacket.emit(packet, address, 0)
        #     return

        # if jpacket["TT"] == "ST":
        #     #if  not self.checkTranForBalance(jpacket):
        #         #return
        #     self.transactionMemory.add(packet)
        #     self.floodPacket.emit(packet, address, 0)
        #     return

    def getFreezeTokens(self, wallet, token_type = "VINCI"):
        freezeForVotes = self.redis.zscore("UNTVOTES", wallet)
        if freezeForVotes is None:
            freezeForVotes = 0
        freezeForVotes = freezeForVotes*self.freezeToVT

        if self.redis.zscore("APPLICANTS", wallet) is None:
            freezeForApplicant = 0
        else:
            freezeForApplicant = self.freezeToAT

        return freezeForApplicant + freezeForVotes

    def garbageCollector(self):
        bheight = self.mongo.vncchain.find().count()
        if bheight is None:
            bheight = 0

        endBlock = bheight - 12*60
        if endBlock < 0:
            endBlock = 0

        oldTxs = self.redis.zrangebyscore("COMPLETE TRANSACTIONS", '0', str(endBlock))

        for tran in oldTxs:
            print("SEARCH:", "TRANSACTIONS:" + tran.decode())
            tranbody = self.redis.get("TRANSACTIONS:" + tran.decode())

            if tranbody is None:
                continue

            jtranbody = json.loads(tranbody)
            jtranbody.update({"_id": tran.decode()})
            self.mongo.complete.save(jtranbody)
            self.redis.delete("TRANSACTIONS:" + tran.decode())
            self.redis.zrem("COMPLETE TRANSACTIONS", tran)

        oldFTxs = self.redis.zrange("FAILED TRANSACTIONS", 0, -1)
        for ftran in oldFTxs[0:int(len(oldFTxs)/2)]:
            self.redis.zrem("FAILED TRANSACTIONS", ftran)

        return True


    def updateFee(self):
        #bheight = self.redis.zcard("VNCCHAIN")
        bheight = self.mongo.vncchain.find().count()

        if bheight is None:
            bheight = 0

        TrXcount = len(self.redis.zrange("COMPLETE TRANSACTIONS", bheight - 1000, bheight))/1000

        if bheight > self.freeZoneHeight:
            if TrXcount >= 10000:
                self.fee = 0.0001

            if TrXcount >= 5000 or TrXcount < 10000:
                self.fee = 0.001

            if TrXcount >= 3000 or TrXcount < 5000:
                self.fee = 0.003

            if TrXcount >= 100 or TrXcount < 3000:
                self.fee = 0.005

            if TrXcount < 100:
                self.fee = 0.01


        print("CURRENT FEE IN THIS TIME:", self.fee)
        return

    def beApplicant(self):
        if self.stemAddress is None:
            return False

        packet = JsonPackets.wantBeApplicant(self.cryptor)
        #print ("SEND BEAPP", self.stemAddress)
        self.sendPacket.emit(self.stemAddress, packet, 1)

    def checkTranForBalance(self, jtran:dict):
        sender = jtran["SENDER"]
        type = jtran["TTOKEN"]
        count = jtran["CTOKEN"]
        walletBalance = self.BALANCE.get(sender)

        if count < 0:
            return False
        if type != self.currentTokenType:
            return False
        if walletBalance is None:
            return False
        if walletBalance < count:
            return False
        return True

    def checkTranForBalanceAttrs(self, sender, type, count):
        walletBalance = self.BALANCE.get(sender)

        if count < 0:
            return False
        if type != self.currentTokenType:
            return False
        if walletBalance is None:
            return False
        if walletBalance < count:
            return False
        return True


    def sliceFloat(self, money:float):
        return "{0:.8f}".format(money)

    def balanceMainWorkRedis(self, bchain:list):
        for jblock in bchain:
            #jblock = json.loads(block)

            if jblock['TT'] == "BL":
                trans = jblock['TRANSACTIONS']
                if self.redis.zscore("BALANCE:VINCI", jblock['SENDER']) is None:
                    self.redis.zadd("BALANCE:VINCI", 0, jblock['SENDER'])

                blockSenderBalance = self.redis.zscore("BALANCE:VINCI", jblock['SENDER'])
                blockSenderBalance += self.blockReward
                print("BALANCE_BHEIGHT", jblock['BHEIGHT'])
                print("FREEZZE:", self.getFreezeTokens(jblock['SENDER']))
                print("ADDING BALANCE VINCI TO VALIDATOR:", blockSenderBalance - self.getFreezeTokens(jblock['SENDER']), jblock['SENDER'])
                self.redis.zadd("BALANCE:VINCI", blockSenderBalance, jblock['SENDER'])

                for tran in trans:
                    if tran["TT"] == "ST" and self.currentTokenTypes.count(tran["TTOKEN"]) and float(tran["CTOKEN"]) > 0:
                        tokenPrefix = tran["TTOKEN"]
                        if tran['SENDER'] == tran['RECEIVER']:
                            continue
                        if self.redis.zscore("BALANCE:" + tokenPrefix, tran['SENDER']) is None:
                            self.redis.zadd("BALANCE:" + tokenPrefix, 0, tran['SENDER'])
                        if self.redis.zscore("BALANCE:" + tokenPrefix, tran['RECEIVER']) is None:
                            self.redis.zadd("BALANCE:" + tokenPrefix, 0, tran['RECEIVER'])
                        senderBalance = self.redis.zscore("BALANCE:" + tokenPrefix, tran['SENDER'])
                        receiverBalance = self.redis.zscore("BALANCE:" + tokenPrefix, tran["RECEIVER"])
                        senderBalance = senderBalance - float(tran["CTOKEN"])
                        receiverBalance = receiverBalance + float(tran["CTOKEN"])
                        self.redis.zadd("BALANCE:" + tokenPrefix, self.sliceFloat(senderBalance), tran["SENDER"])
                        self.redis.zadd("BALANCE:" + tokenPrefix, self.sliceFloat(receiverBalance), tran["RECEIVER"])

                    if tran["TT"] == "ET" and self.currentTokenTypes.count(tran["STT"]) and self.currentTokenTypes.count(tran["RTT"]) and float(tran["STC"]) > 0 and float(tran["RTC"]) > 0:
                        tokenSenderPrefix = tran["STT"]
                        tokenReceiverPrefix = tran["RTT"]

                        if tran['SENDER'] == tran['RECEIVER']:
                            continue

                        #MONEY SEND
                        if self.redis.zscore("BALANCE:" + tokenSenderPrefix, tran['SENDER']) is None:
                            self.redis.zadd("BALANCE:" + tokenSenderPrefix, 0, tran['SENDER'])
                        if self.redis.zscore("BALANCE:" + tokenSenderPrefix, tran['RECEIVER']) is None:
                            self.redis.zadd("BALANCE:" + tokenSenderPrefix, 0, tran['RECEIVER'])
                        senderBalance = self.redis.zscore("BALANCE:" + tokenSenderPrefix, tran['SENDER'])
                        receiverBalance = self.redis.zscore("BALANCE:" + tokenSenderPrefix, tran["RECEIVER"])
                        senderBalance = senderBalance - float(tran["STC"])
                        receiverBalance = receiverBalance + float(tran["STC"])
                        self.redis.zadd("BALANCE:" + tokenSenderPrefix, self.sliceFloat(senderBalance), tran["SENDER"])
                        self.redis.zadd("BALANCE:" + tokenSenderPrefix, self.sliceFloat(receiverBalance), tran["RECEIVER"])

                        #GOODS SEND
                        if self.redis.zscore("BALANCE:" + tokenReceiverPrefix, tran['RECEIVER']) is None:
                            self.redis.zadd("BALANCE:" + tokenReceiverPrefix, 0, tran['RECEIVER'])
                        if self.redis.zscore("BALANCE:" + tokenReceiverPrefix, tran['SENDER']) is None:
                            self.redis.zadd("BALANCE:" + tokenReceiverPrefix, 0, tran['SENDER'])

                        receiverBalance = self.redis.zscore("BALANCE:" + tokenReceiverPrefix, tran['RECEIVER'])
                        senderBalance = self.redis.zscore("BALANCE:" + tokenReceiverPrefix, tran["SENDER"])
                        receiverBalance = receiverBalance - float(tran["RTC"])
                        senderBalance = senderBalance + float(tran["RTC"])

                        self.redis.zadd("BALANCE:" + tokenReceiverPrefix, self.sliceFloat(receiverBalance), tran["RECEIVER"])
                        self.redis.zadd("BALANCE:" + tokenReceiverPrefix, self.sliceFloat(senderBalance), tran["SENDER"])

    def checkBalance(self, updateLen = -1):

        #bheight = self.redis.zcard("VNCCHAIN")
        #pymongo_cursor = self.mongo.vncchain.find().sort("BHEIGHT", pymongo.ASCENDING).limit(1)
        #bheight = dict(pymongo_cursor).get("BHEIGHT")
        bheight = self.mongo.vncchain.find().count()

        if updateLen == -1:
            print("START:", self.lastCheckBlockBalance, "STOP:", bheight)

            bchain = list(self.mongo.vncchain.find({"BHEIGHT": {"$gte": int(self.lastCheckBlockBalance)}}))
            print("BCH", bchain)

            #bchain = self.redis.zrange("VNCCHAIN", self.lastCheckBlockBalance, bheight)
            self.lastCheckBlockBalance = bheight
            self.balanceMainWorkRedis(bchain)
        else: ### STEP MODE
            step = self.lastCheckBlockBalance

            while step < bheight:
                nextStep = step + self.updateBalanceStep
                if nextStep > bheight:
                    nextStep = bheight

                #bchain = self.redis.zrange("VNCCHAIN", step, nextStep)

                bchain = list(self.mongo.vncchain.find([{"BHEIGHT":{"$gt":step}},{"BHEIGHT":{"$lt":nextStep}}]))
                step = nextStep
                self.balanceMainWorkRedis(bchain)

            self.lastCheckBlockBalance = nextStep
        return

    def run(self):
        while True:
            self.stackMutex.lock()
            if len(self.packetStack):
                packet = self.packetStack.pop(0)
            else:
                self.stackMutex.unlock()
                continue

            self.stackMutex.unlock()
            address = packet[0]
            packet = packet[1]

            #if self.signChecker.checkTran(packet): // Проверка подписи!
            self.handler(address, packet)


if __name__ == '__main__':
    app = QCoreApplication(sys.argv)

    import socket  # To Retrieve our IP address for Test-net purposes

    privateKey = "YOUR PRIVATE NODE KEY"

    # for arg in sys.argv:
    #     if arg == "--privateKey":
    #         if (len(sys.argv) >= sys.argv.index(arg)):
    #             privateKey = sys.argv[sys.argv.index(arg) + 1]
    #         else:
    #             print("Value after --privateKey not found!")
    #             exit(1)
    #
    # if privateKey == None:
    #     print("Private key not found!")
    #     exit(2)

    slave = slaveWorker(socket.gethostbyname(socket.gethostname()), privateKey)

    netEngine = NetEngine()

    app.aboutToQuit.connect(netEngine.onAboutToQuit)
    netEngine.newDataPacket.connect(slave.appendPacketToStack)
    slave.floodPacket.connect(netEngine.floodPacketSignal)
    slave.sendPacket.connect(netEngine.sendPacketSignal)
    slave.setPurifyList.connect(netEngine.setRemoteAddresses)

    garbageCollectorTimer = QTimer()
    garbageCollectorTimer.setInterval(slave.timeToGarbageCollector)
    garbageCollectorTimer.timeout.connect(slave.garbageCollector)
    garbageCollectorTimer.start()

    slave.start()
    netEngine.runReceiver.emit("0.0.0.0")
    sys.exit(app.exec())
