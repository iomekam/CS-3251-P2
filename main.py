from urllib import quote
import requests
from hashlib import sha1
from bencode import *
from twisted.internet import protocol, reactor
import socket
import ipaddress
import struct
from bitstring import *

class State:
       Handshake, Bitfield, Choke, UnChoke, Interested, Have, NotInterested, Request, Piece = range(9)

class EchoClient(protocol.Protocol):
       def __init__(self, message):
           self.message = message
           self.recievedHandshake = False;
           self.bytesLeft = -1
           self.payload = ""
           self.bufferList = []
           self.data = ""
           self.state = State.Handshake
           self.payloadStillFetching = False
           self.hasPayload = False
           self.payloadBit = BitArray()

       toHex = lambda self, x:"0x".join([hex(ord(c))[:].zfill(2) for c in x])
           
       def connectionMade(self):
           self.transport.write(self.message)

       def getMessage(self, data):
              print(data.split("gg"))
              data = [ord(data[0]), ord(data[1]), ord(data[2]), ord(data[3]), ord(data[4])]
              if(data[3] == 1 and data[4] == 0):
                     self.state = State.Choke
              elif(data[3] == 1 and data[4] == 1):
                     self.state = State.UnChoke
              elif(data[3] == 1 and data[4] == 2):
                     self.state = State.Interested
              elif(data[3] == 5 and data[4] == 1):
                     self.state = State.Have
                     self.hasPayload = True
              elif(data[3] == 1 and data[4] == 3):
                     self.state = State.NotInterested
              elif(data[3] == 13 and data[4] == 6):
                     self.state = State.Request
              elif(data[3] == 13 and data[4] == 8):
                     self.state = State.Cancel
              elif(data[4] == 7):
                     self.state = State.Piece
              elif(data[4] == 5):
                     self.state = State.Bitfield
                     self.hasPayload = True

       def getPayload(self, data):
              if(len(data) < self.bytesLeft):
                     self.payload = self.payload + data
                     self.bytesLeft -= len(data)
                     self.payloadStillFetching = True
              else:
                     self.payload = self.payload + data[:self.bytesLeft]
                     data = data[self.bytesLeft:]
                     self.bytesLeft = 0;
                     self.payloadBit = BitArray(self.toHex(self.payload))
                     print(self.payloadBit.bin)
                     self.payloadStillFetching = False
                     self.hasPayload = False
                     return data

       def parseData(self, data):
              if(self.hasPayload and not self.payloadStillFetching):
                     self.getMessage(data[:5])
                     if(self.state == State.Bitfield):
                            self.bytesLeft = ord(data[3]) - 1
                     if(self.state == State.Have):
                            self.bytesLeft = 4
                     self.getPayload(data[5:])
              elif(self.hasPayload and self.payloadStillFetching):
                     data = self.getPayload(data)
                     if(not self.payloadStillFetching):
                            self.getMessage(data[:5])
                            self.parseData(data)
              elif(not self.hasPayload and not self.payloadStillFetching):
                     print("No payload")
                     self.getMessage(data[:5])
                     if(len(data) > 5):
                            self.parseData(data[:5])
       def dataReceived(self, data):
           self.data = self.data + data
           print("hit")
           if(self.state == State.Handshake):
                  self.hasPayload = True
                  self.parseData(data[68:])
           else:
                  self.parseData(data)
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

        print left

        payload = {'info_hash':self.infoHash, 'peer_id':self.peerID, 'uploaded':uploaded, "port":port, 'downloaded':downloaded, "left":left, 'event':event, "compact":compact, "ip":socket.gethostbyname(socket.gethostname())}
        r = requests.get(announce, params=payload)
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
        print(len(handshake))
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
