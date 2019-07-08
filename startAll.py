from crypto.cryptoFernet import cryptoFernet
import sys, os

if __name__ == '__main__':

    if len(sys.argv) != 2:
        print("Need 2 attributes, receive ", len(sys.argv))
        exit(1)

    crf = cryptoFernet(sys.argv[1])
    pFile = open("PRIVATE", "r")
    token = pFile.read().encode()
    private = crf.decrypt(token).decode()
    print(private)

    print('python ./sharding/VINCI/slaveNode.py --privateKey ' + private)
    os.system('/var/data/rest/goVncNet -privateKey=' + private)
