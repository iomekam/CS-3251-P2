from urllib import quote
import requests
from hashlib import sha1
from bencode import *
from twisted.internet import protocol, reactor
import socket
import ipaddress
import struct

class EchoClient(protocol.Protocol):
       def __init__(self, message):
           self.message = message

       def connectionMade(self):
           self.transport.write(self.message)

       def dataReceived(self, data):
           print(data.split("x"))
           print("")
           message = struct.pack("!3x1c1c", "1", "2")

               #print(struct.unpack("!3x1c1c", data))
           #self.transport.write(message)
           
           #self.transport.loseConnection()
           
class EchoFactory(protocol.ClientFactory):
        def __init__(self, message):
               self.message = message
               
        def buildProtocol(self, addr):
               return EchoClient(self.message)

        def clientConnectionFailed(self, connector, reason):
               print reason
               reactor.stop()

        def clientConnectionLost(self, connector, reason):
               print "Connection lost."
               reactor.stop()

class BitClient:
    def __init__(self, bDict, peerID):
        self.peerID = peerID
        self.bDict = bDict
        self.infoHash = self.getInfoHash()
    def getInfoHash(self):
        return sha1(bencode(self.bDict["info"])).digest()
    
    def getPeerID(self):
        return self.peerID
    def connectToTracker(self):
        announce = self.bDict["announce"]
        port = 6900
        uploaded = 0
        downloaded = 0
        left = self.bDict["info"]["piece length"]
        event = "started"
        compact = 1

        payload = {'info_hash':self.infoHash, 'peer_id':self.peerID, 'uploaded':uploaded, "port":port, 'downloaded':downloaded, "left":left, 'event':event, "compact":compact, "ip":socket.gethostbyname(socket.gethostname())}
        r = requests.get(announce, params=payload)
        print r.url
        return bdecode(r.text)
        
    def getIPPortList(self):
        ip = []
        request = self.connectToTracker()
        for index in range(0, len(request["peers"]), 6):
            b = bytearray(request["peers"][index:index+4], encoding="latin1")
            port = ord(request["peers"][index+4])*256 + (ord(request["peers"][index+5]))
            ip.append((ipaddress.IPv4Address(str(b)).exploded, port))
        return ip
    
    def sendHandshake(self):
        handshake = "\x13BitTorrent protocol" + struct.pack("!8x20s20s", self.infoHash, self.peerID)
        self.sendToSinglePeer("127.0.0.1", 45030, handshake)

    def sendToSinglePeer(self, ip, port, message):
        reactor.connectTCP(ip, port, EchoFactory(message))
        reactor.run()

def main(filename):
    file = open(filename, 'rb')
    benDict = bdecode(file.read())
    peerID = "-IO0001-012345678901"
    client = BitClient(benDict, peerID)

    client.getIPPortList()
    client.sendHandshake()
