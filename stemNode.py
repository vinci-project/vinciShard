from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QTimer
import sys
from random import randint, sample
import redis, os
import json

from netTools import NetEngine
from vncCrypto.signChecker import SignChecker
from vncCrypto.mrkl import VncTree
from jsonMaker import JsonPackets
from vncCrypto import VncCrypto
from settings.netSettings import NetSettings

class Stem(QObject):
    floodPacket = pyqtSignal(str, str, int)
    sendPacket = pyqtSignal(str, str, int)
    setPurifyList = pyqtSignal(list)
    signalToMakePurifi = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.slavesNodes = []
        self.slave_max_count = 20
        self.blocks_in_genesis = 10000000

        self.redis_host = os.getenv("REDIS_PORT_6379_TCP_ADDR") or 'localhost'
        self.redis_port = os.getenv("REDIS_PORT_6379_TCP_PORT") or '6379'

        self.redis = redis.StrictRedis(self.redis_host, self.redis_port, db=0)

        self.signChecker = SignChecker()
        self.lastCheckBlockBalance = 0
        self.BALANCE = {}
        self.currentTokenType = "VINCI"
        self.blockReward = 10
        self.timeToBlock = 7*1000 #5 seconds
        self.lastChoiseNode = ("ip","puk")
        #------------------------------------------------
        #self.cryptor.generateKeys()
        self.cryptor = VncCrypto()
        pKey = "TEST PUBLIC KEY"
        self.cryptor.setPrivateKey(pKey)
        self.redis.flushall()
        #------------------------------------------------
        # self.tokenomics.VINCI_mas = 23000000
        # self.tokenomics.vote_price = 1000
        # self.tokenomics.vote_threshold = 15 #15 percent
        # self.tokenomics.vncsphere_pkey = "MIGEAgEAMBAGByqGSM49AgEGBSuBBAAKBG0wawIBAQQg2T2hOBOge31fUR2WupCLA9SM/K4hBM/pLAWpj/YMOTKhRANCAATL3O9VXOpQSFWLbXHpIHinepF6iO6EPOo1ae5ykS0ymFCzB/1Y676DbEkpcQnYbn7iAYsXQiaz/FRUPCrndO9p"
        # self.tokenomics.min_fee = 0.01
        # self.tokenomics.max_fee = 0.1
        # self.tokenomics.slave_reward = 0.14
        # self.tokenomics.stem_reward = 0.007
        #------------------------------------------------

    def createTest(self):
        self.benchmark.generateStemResult()

    def chooserPacket(self):
        print("CHOOSER")
        blockchain_height = self.redis.zcard("VNCCHAIN")
        print("CHOOSER PAKET BH:", blockchain_height)
        #chooseNode = self.slavesNodes[randint(0, (len(self.slavesNodes) - 1))]
        chooseNode = "127.0.0.3"
        packet = JsonPackets.chooserTransaction(self.cryptor, blockchain_height)
        self.sendPacket.emit(chooseNode, packet, 1)
        return

    @pyqtSlot(str, str)
    def handler(self, address: str, packet: str):
        if not self.signChecker.checkTran(packet):
             return

        jpacket = json.loads(packet)

        if jpacket["TT"] == "ASB":
            blockchain_height = self.redis.zcard("VNCCHAIN")

            if blockchain_height < jpacket["NBH"]:
                packet = JsonPackets.badAnswer(self.cryptor)
            else:
                data = self.redis.zrange("VNCCHAIN", jpacket["NBH"], jpacket["NBH"] + 1)
                if len(data) == 0:
                    packet = JsonPackets.badAnswer(self.cryptor)
                else:
                    packet = JsonPackets.createCommitBlockForResend(self.cryptor, data[0])

            self.sendPacket.emit(address, packet, 1)
            return



        if jpacket["TT"] == "CB":
            blockchain_height = self.redis.zcard("VNCCHAIN")

            # RESEND TO ALL NODES NEW BLOCK #
            temp = jpacket['BLOCK']

            signs = temp.get("SIGNATURE")

            newBlock = json.dumps(temp, separators=(',', ':'))
            newBlock = JsonPackets.createCommitBlockForResendHash(self.cryptor, newBlock, blockchain_height, signs)
            self.floodPacket.emit(newBlock, str(), 1)
            # RESEND TO ALL NODES NEW BLOCK #

            self.redis.zadd("VNCCHAIN", blockchain_height, json.dumps(jpacket['BLOCK'], separators=(',', ':')))
            blockchain_height += 1
            if blockchain_height % self.blocks_in_genesis == 0:
                self.signalToMakePurifi.emit()

            self.checkBalance()
            return


        if jpacket["TT"] == "MBR":
            if self.benchmark.testNodeResult(jpacket["START"], jpacket["RESULT"], jpacket["SENDER"]):
                print ("YOU WIN!")
            else:
                print ("YOU FAIL!")
            return

        if jpacket["TT"] == "BAN":
            return

        if jpacket["TT"] == "WBA": #WANT BE APPLICANT
            benchUUID = self.benchmark.getStemResult(jpacket["SENDER"])
            print("RECIVE BEAPP")
            if benchUUID is not None:
                packet = JsonPackets.benchmarkTesting(self.cryptor, benchUUID)
                print("SEND BT")
                self.sendPacket.emit(address, packet, 1)
            else:
                print("NO ANY TEST")
            return

        # ========================= FOR SUPER STEM ===============================

        if jpacket["TT"] == "GYID": # GIVE YOUR IDENTITY
            packet = JsonPackets.universalPacket(self.cryptor, "TMID", self.currentTokenType)
            self.sendPacket.emit(address, packet, 1)
            return

        if jpacket["TT"] == "GYBL": # GIVE YOUR BLOCK
            blockchain_height = self.redis.zcard("VNCCHAIN")

            if blockchain_height < jpacket["NBH"]:
                packet = JsonPackets.badAnswer(self.cryptor)
            else:
                data = self.redis.zrange("VNCCHAIN", jpacket["NBH"], -1)
                packet = JsonPackets.universalPacket(self.cryptor, "MBL", data)

            self.sendPacket.emit(address, packet, 1)
            return

        # END OF FUNC
        return

    def balanceMainWorkRedis(self, bchain:list):
        for block in bchain:
            jblock = json.loads(block)

            if jblock['TT'] == "BL":
                trans = jblock['TRANSACTIONS']
                if self.redis.zscore("BALANCE", jblock['SENDER']) is None:
                    self.redis.zadd("BALANCE", 0, jblock['SENDER'])

                blockSenderBalance = self.redis.zscore("BALANCE", jblock['SENDER'])
                blockSenderBalance += self.blockReward
                print("ADDING BALANCE TO VALIDATOR:", blockSenderBalance, jblock['SENDER'])
                self.redis.zadd("BALANCE", blockSenderBalance, jblock['SENDER'])

                for tran in trans:
                    if tran["TT"] == "ST" and tran["TTOKEN"] == self.currentTokenType and float(tran["CTOKEN"]) > 0:
                        if self.redis.zscore("BALANCE", tran['SENDER']) is None:
                            self.redis.zadd("BALANCE", 0, tran['SENDER'])

                        if self.redis.zscore("BALANCE", tran['RECEIVER']) is None:
                            self.redis.zadd("BALANCE", 0, tran['RECEIVER'])

                        senderBalance = self.redis.zscore("BALANCE", tran['SENDER'])
                        receiverBalance = self.redis.zscore("BALANCE", tran["RECEIVER"])
                        senderBalance = senderBalance - float(tran["CTOKEN"])
                        receiverBalance = receiverBalance + float(tran["CTOKEN"])
                        self.redis.zadd("BALANCE", senderBalance, tran["SENDER"])
                        self.redis.zadd("BALANCE", receiverBalance, tran["RECEIVER"])

    def checkBalance(self, updateLen = -1):
        bheight = self.redis.zcard("VNCCHAIN")

        if updateLen == -1:
            bchain = self.redis.zrange("VNCCHAIN", self.lastCheckBlockBalance, bheight)
            self.lastCheckBlockBalance = bheight
            self.balanceMainWorkRedis(bchain)
        else: ### STEP MODE
            step = 0

            while step < bheight:
                nextStep = step + updateLen
                if nextStep > bheight:
                    nextStep = bheight

                bchain = self.redis.zrange("VNCCHAIN", step, nextStep)
                step = nextStep
                self.balanceMainWorkRedis(bchain)
        return

    def purifierMaker(self):
        blockchain_height = self.redis.zcard("VNCCHAIN")

        purifiBlock = str()

        if blockchain_height == 0:
            netSettings = NetSettings()


            print(netSettings.keysList)
            print(netSettings.purifierList)

            purifiBlock = JsonPackets.createFirstPurifierBlock(self.cryptor, netSettings.purifierList, netSettings.keysList, blockchain_height)
            jpurify = json.loads(purifiBlock)
            print(purifiBlock)
            purify_list = jpurify["CLEAN_LIST"]
            print(purify_list)

            if len(purify_list) != 0:
                self.slavesNodes = purify_list
                self.setPurifyList.emit(purify_list)
                self.redis.zadd("VNCCHAIN", blockchain_height, purifiBlock)
                self.floodPacket.emit(purifiBlock, str(), 1)
        else:
            if blockchain_height % self.blocks_in_genesis == 0:
                last_genesis_block_number = ((blockchain_height // self.blocks_in_genesis) * self.blocks_in_genesis) - self.blocks_in_genesis
                genesis_zone = self.redis.zrange("VNCCHAIN", last_genesis_block_number + 1, -1)
                applicant_transactions = []
                for block in genesis_zone:
                    jblock = json.loads(block)
                    for tran in jblock["TRANSACTIONS"]:
                        if isinstance(tran, dict):
                            jtran = tran
                        else:
                            jtran = json.loads(tran)

                        if jtran["TT"] != "AT":
                            continue
                        else:
                            if applicant_transactions.count(jtran["IPADR"]) == 0:
                                applicant_transactions.append(jtran["IPADR"])

                if len(applicant_transactions) == 0:
                    self.setPurifyList.emit(self.slavesNodes)
                    purifiBlock = JsonPackets.createPurifierBlock(self.cryptor, self.slavesNodes, blockchain_height)
                    self.redis.zadd("VNCCHAIN", blockchain_height, purifiBlock)
                else:
                    if len(applicant_transactions) < self.slave_max_count:
                        self.slavesNodes = list(set(applicant_transactions))
                    else:
                        self.slavesNodes = list(set(sample(applicant_transactions, self.slave_max_count)))

                    self.setPurifyList.emit(self.slavesNodes)
                    purifiBlock = JsonPackets.createPurifierBlock(self.cryptor, self.slavesNodes, blockchain_height)
                    self.redis.zadd("VNCCHAIN", blockchain_height, purifiBlock)

            else:
                last_genesis_block_number = (blockchain_height // self.blocks_in_genesis) * self.blocks_in_genesis
                print("LAST NUMBER:", last_genesis_block_number)
                genesis_zone = self.redis.zrange("VNCCHAIN", last_genesis_block_number, last_genesis_block_number)
                print("GENESIS: " + str(genesis_zone[0]))
                last_genesis_block = json.loads(genesis_zone[0].decode())
                self.slavesNodes = list(set(last_genesis_block["CLEAN_LIST"]))
                self.setPurifyList.emit(self.slavesNodes)
                purifiBlock = genesis_zone[0].decode()

        print ("RESEND ", purifiBlock)
        self.floodPacket.emit(purifiBlock, str(), 1)

if __name__ == '__main__':
    app = QCoreApplication(sys.argv)
    #--------------------------------------------
    stem = Stem()

    netEngine = NetEngine()

    app.aboutToQuit.connect(netEngine.onAboutToQuit)
    netEngine.newDataPacket.connect(stem.handler)
    stem.sendPacket.connect(netEngine.sendPacketSignal)
    stem.floodPacket.connect(netEngine.floodPacketSignal)

    netEngine.runReceiver.emit("127.0.0.1")
    stem.setPurifyList.connect(netEngine.setRemoteAddresses)
    stem.signalToMakePurifi.connect(stem.purifierMaker)

    stem.purifierMaker()

    nodeChooser = QTimer()
    nodeChooser.setInterval(stem.timeToBlock)
    nodeChooser.timeout.connect(stem.chooserPacket)
    nodeChooser.start()
    #--------------------------------------------
    sys.exit(app.exec())
