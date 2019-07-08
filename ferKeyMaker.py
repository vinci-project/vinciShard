from crypto.cryptoFernet import cryptoFernet
import sys, os

if __name__ == '__main__':

    if len(sys.argv) != 3:
        print("Need 2 attributes, receive ", len(sys.argv))
        exit(1)

    if len(sys.argv[1]) != 64: #Private Key lenght
        print("PrivateKey bad format - need 64 characters, receive ", len(sys.argv[1]))
        exit(2)

    crf = cryptoFernet(sys.argv[2])
    token = crf.crypt(sys.argv[1])

    pFile = open("PRIVATE", "w")
    pFile.write(token.decode())