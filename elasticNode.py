from PyQt5.QtCore import QCoreApplication
from PyQt5.QtCore import QObject
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtCore import QTimer
import sys
from random import randint
import redis
import json
import time, os
from datetime import date, datetime

from vncCrypto.mrkl import VncTree
from elastLog.elalog import elalog
from pymongo import MongoClient
import pymongo

class ENode(QObject):
    def __init__(self):
        super().__init__()

        self.redis_host = os.getenv("REDIS_PORT_6379_TCP_ADDR") or 'localhost'
        self.redis_port = os.getenv("REDIS_PORT_6379_TCP_PORT") or '6379'
        self.mongo_host =  'localhost'
        self.mongo_port =  27017

        # SAVE CURRENT DATE
        tempDate = datetime.now().strftime("%Y.%m.%d")
        # SAVE CURRENT DATE
        self.elka = elalog(tempDate)
        self.lastDate = tempDate # CONFIRM ONLY AFTER CREATE INDEX!

        #self.redis = redis.StrictRedis()
        self.redis = redis.StrictRedis(self.redis_host, self.redis_port, db=1)
        self.mongo_conn = MongoClient(self.mongo_host, self.mongo_port)
        self.mongo = self.mongo_conn.vncsphere
        #======================================
        self.elastNodeId = "VNC"
        self.blockChainStepLog = 10
        self.lastLogBlock = 0
        self.timeToSaveStat = 5*1000
        self.timeToTestDate = 10000
        self.timeToValid = 60*60*1000

    def sendElasticClientsInfo(self):
        jsonMas = []

        for i in range(0, 500):
            ip = str(randint(0, 255)) + "." + str(randint(0, 255)) + "." + str(randint(0, 255)) + "." + str(randint(0, 255))

            if randint(0, 50) == 0:
                client_type = "validator"
            else:
                client_type = "user"

            eljson = {"_index": "clients", "_type": "clients", "pipeline": "geoip",
                      "_source": {"@dtime": int(time.time()), "ip": ip, "public_key": VncTree.hash(ip),
                                  "client_type": client_type}}
            jsonMas.append(eljson)

        eljson = {"_index": "clients", "_type": "clients", "pipeline": "geoip",
                  "_source": {"@dtime": int(time.time()), "ip": "54.93.72.87",
                              "public_key": "0323f264fd64a684db1e36a2c97b58867e0625f797008206216576fea2114bdbca",
                              "client_type": "validator"}}

        jsonMas.append(eljson)

        eljson = {"_index": "clients", "_type": "clients", "pipeline": "geoip",
                  "_source": {"@dtime": int(time.time()), "ip": "202.51.137.78",
                              "public_key": "0323f264fd64a684db1e36a2c97b58867e0625f797008206216576fea2114bdbca",
                              "client_type": "validator"}}
        jsonMas.append(eljson)

        file = open("JS.txt", "w")
        file.write(json.dumps(jsonMas, separators=(',', ':')))

        self.elka.elasticClients(jsonMas)

    def eLog(self):
        while True:
            bchainHeight = self.mongo.vncchain.find().count()

            if self.lastLogBlock == bchainHeight: #FULL LOG COMPLETE!
                break

            blocks = list(self.mongo.vncchain.find({"BHEIGHT": int(self.lastLogBlock)}))
            #blocks = self.redis.zrange("VNCCHAIN", self.lastLogBlock, self.lastLogBlock)
            self.lastLogBlock += 1
            self.__eLog(blocks)


    def eLogBalance(self):
        print("START BALANCE")
        bchainHeight = self.mongo.vncchain.find().count()
        if self.lastLogBlock == bchainHeight:  # FULL LOG COMPLETE!
            print("START BALANCE TRUE EXIT")
            return True

        users = self.redis.zrange("BALANCE", 0, -1)
        bal = {}

        print("USERS:", len(users))

        for user in users:
            balance = self.redis.zscore("BALANCE", user)
            bal.update({user.decode(): balance})

        print(bal)

        self.elka.elasticBalanceHistory(bal)

        return True


    def __eLog(self, blist):
        for block in blist:

            if isinstance(block, bytes):
                jblock = json.loads(block.decode())
            else:
                if isinstance(block, dict):
                    jblock = block
                else:
                    jblock = json.loads(block)


            print("SAVE BLOCK: ", jblock["BHEIGHT"])

            if jblock["TT"] == "BL":
                self.elka.elasticBlock(int(time.time()), jblock["SENDER"], int(jblock["TCOUNT"]), jblock["SIGNATURE"], VncTree.hash(block), jblock["BHEIGHT"])

                trans = jblock["TRANSACTIONS"]
                obtrans = []
                for tran in trans:
                    if tran["TT"] == "ST":
                        if ENode.isfloat(tran["CTOKEN"]) is False:
                            print("ERROR! BAD TOKEN COUNT, NOT FLOAT!", tran["CTOKEN"])
                            continue

                        eljson = {"_index": "transactions-" + self.lastDate, "_type": "transactions-" + self.lastDate,
                                  "_source": {  "@dtime": int(tran["TST"]),
                                                "block": jblock["BHEIGHT"],
                                                "sender": tran["SENDER"],
                                                "receiver": tran["RECEIVER"],
                                                "token_count": float(tran["CTOKEN"]),
                                                "token_type": tran["TTOKEN"],
                                                "hash": VncTree.hash(json.dumps(tran, separators=(',', ':')))
                                    }
                                  }

                        obtrans.append(eljson)

                self.elka.elasticTransaction(obtrans)

        return True

    @staticmethod
    def isfloat(value):
        try:
            float(value)
            return True
        except:
            return False

    def testDate(self):
        # SAVE CURRENT DATE
        tempDate = datetime.now().strftime("%Y.%m.%d")
        if tempDate == self.lastDate:
            return
        else:
            self.elka = elalog(tempDate)
            self.lastDate = tempDate # CONFIRM ONLY AFTER CREATE INDEX!

        return


if __name__ == '__main__':
    app = QCoreApplication(sys.argv)
    #--------------------------------------------

    eNode = ENode()
    #eNode.lastLogBlock = eNode.elka.getLastEBlock() + 1

    eNode.sendElasticClientsInfo()

    # validUpdater = QTimer()
    # validUpdater.setInterval(eNode.timeToValid)
    # validUpdater.timeout.connect(eNode.sendElasticClientsInfo)
    # validUpdater.start()
    #
    # dateUpdater = QTimer()
    # dateUpdater.setInterval(eNode.timeToTestDate)
    # dateUpdater.timeout.connect(eNode.testDate)
    # dateUpdater.start()
    #
    # nodeChooser = QTimer()
    # nodeChooser.setInterval(eNode.timeToSaveStat)
    # nodeChooser.timeout.connect(eNode.eLog)
    # nodeChooser.start()
    #
    # nodeChooser2 = QTimer()
    # nodeChooser2.setInterval(eNode.timeToSaveStat)
    # nodeChooser2.timeout.connect(eNode.eLogBalance)
    # nodeChooser2.start()
    #--------------------------------------------
    sys.exit(app.exec())