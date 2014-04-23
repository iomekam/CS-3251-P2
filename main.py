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
       Handshake, Bitfield, Choke, UnChoke, Interested, Have, NotInterested, Request, Piece, KeepAlive, Bad = range(11)

class EchoClient(protocol.Protocol):
       def __init__(self, message, bDict):
           self.message = message
           self.recievedHandshake = False;
           self.bytesLeft = -1
           self.payload = ""
           self.bufferList = []
           self.data = ""
           self.state = State.Handshake
           self.payloadStillFetching = False
           self.hasPayload = False
           self.pieceNum = len(bDict["info"]["pieces"]) / 20
           self.payloadBit = BitArray("0xF"*self.pieceNum)
           self.nextMessage = False
           self.bDict = bDict
           self.pieceList = []
           self.noPiecePresent = []
           self.requestList = []
           self.index = 0;
           self.pieceDone = False;
           self.pLength = int(bDict["info"]["piece length"]);
           self.endLength = int(bDict["info"]["length"]) % self.pLength
           if(self.endLength == 0):
                  self.endLength = self.pLength
           print "aaa", int(bDict["info"]["length"])
           print "endlength", self.endLength
           self.pieceBuffer = 2**14
           self.pieceRemaining = self.pLength

       toHex = lambda self, x:"0x".join([hex(ord(c))[:].zfill(2) for c in x])
           
       def connectionMade(self):
           self.transport.write(self.message)

       def getMessage(self, data):
              print(data.split("gg"))
              if(data == '' or len(data) < 4):
                     self.state = State.Bad
                     return
                    
              data = [ord(data[0]), ord(data[1]), ord(data[2]), ord(data[3]), ord(data[4])]
              if(data[3] == 1 and data[4] == 0):
                     self.state = State.Choke
              elif(data[3] == 1 and data[4] == 1):
                     self.state = State.UnChoke
                     self.hasPayload = False
              elif(data[3] == 1 and data[4] == 2):
                     self.state = State.Interested
              elif(data[3] == 5 and data[4] == 4):
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
                     self.hasPayload = True
              elif(data[4] == 5):
                     self.state = State.Bitfield
                     self.hasPayload = True
              else:
                      self.state = State.Bad
                      self.hasPayload = False

       def getPayload(self, data):
              if(len(data) < self.bytesLeft):
                     self.payload = self.payload + data
                     self.bytesLeft -= len(data)
                     if(self.state == State.Piece):
                            self.pieceBuffer -= len(data)
                     self.payloadStillFetching = True
                     self.nextMessage = False
              else:
                     self.payload = self.payload + data[:self.bytesLeft]
                     data = data[self.bytesLeft:]
                     self.bytesLeft = 0;
                     if(self.state == State.Bitfield):    
                            self.payloadBit = BitArray(self.toHex(self.payload))
                     if(self.state == State.Have):
                            bitA = BitArray(self.toHex(self.payload)).int
                            print bitA
                            self.payloadBit.set(True, bitA)
                     if(self.state == State.Piece):
                            isTrue = struct.unpack("!20s", sha1(self.payload).digest()) == struct.unpack("!20s", self.bDict["info"]["pieces"][20*self.index:20 + 20*self.index ])
                            print isTrue

                            if(isTrue):
                                   self.pieceList[self.index] = self.payload
                            else:
                                   self.noPiecesPresent.append(self.index)
                            self.pieceDone = True
                            #print struct.unpack("!20s", sha1(self.payload).digest())
                            #print self.bDict["info"]["pieces"][0:20]
                            #print struct.unpack("!20s", self.bDict["info"]["pieces"][:20])
                            print len(self.payload)#.split("gg")

                            if(len(self.requestList) == 0):
                                f = open(self.bDict["info"]["name"], "wb")
                                for item in self.pieceList:
                                    if(item != None):
                                        f.write(item)
                                    else:
                                        print "Nooo"
                                f.close()
                                
                     self.payloadStillFetching = False
                     self.hasPayload = False
                     self.nextMessage = True
                     self.payload = ""
                     
              return data
       def sendInterested(self):
              message = struct.pack("!IB", 1, 2 )
              self.transport.write(message)
              print("wrote")
       def sendRequest(self, index, offset):
              print "OF", offset
              print "I", index
              message = struct.pack("!IBIII", 13, 6, int(index), int(offset), 2**14)
              self.transport.write(message)
       def makeRequest(self):
              for i in range(self.pieceNum - 10, self.pieceNum):
                     if(self.payloadBit[i]):
                            self.requestList.append(i)
                     else:
                            self.noPiecePresent.append(i)
       def getNextRequest(self):
              self.requestList.reverse()
              index = self.requestList.pop()
              self.requestList.reverse()

              return index
              
       def parseData(self, data):
              if(self.state != State.Piece or self.nextMessage):
                     self.getMessage(data[:5])
              if(self.hasPayload and not self.payloadStillFetching):
                     if(self.state == State.Bitfield):
                            self.bytesLeft = ord(data[3]) - 1
                     if(self.state == State.Have):
                            self.bytesLeft = 4
                     if(self.state == State.Piece):
                            self.bytesLeft = self.pLength
                            self.pieceBufferer = 2**14
                            if(self.requestList == 0):
                                   self.bytesLeft = self.endLength
                            data = data[8:]
                            #print data.split("dd")
                     data = self.getPayload(data[5:])
              elif(not self.nextMessage and self.payloadStillFetching):
                     if(self.state == State.Piece and self.pieceBuffer == 2**14):
                            data = data[13:]
                     data = self.getPayload(data)
              elif(not self.hasPayload and not self.payloadStillFetching):
                     print("No payload")
                     self.nextMessage = True

              if(self.state == State.Piece and self.pieceBuffer == 0):
                     self.pieceBuffer = 2**14
                     base = self.pLength
                     if(len(self.requestList) == 0):
                            base = self.endLength
                            print "base:", base
                     self.sendRequest(self.index, base - self.bytesLeft)
              if(self.state == State.UnChoke):
                     self.makeRequest()
                     self.index = self.getNextRequest()
                     print self.index
                     self.sendRequest(self.index, 0)

              if(self.state == State.Bad):
                     data = data[5:]
              
              if(self.nextMessage):
                     if(len(data) > 5):
                            self.parseData(data)
              if(self.pieceDone and len(self.requestList) != 0):
                     self.pieceDone = False
                     self.index = self.getNextRequest()
                     print self.index
                     self.sendRequest(self.index, 0)
                                
       def dataReceived(self, data):
           self.data = self.data + data
           if(self.state == State.Handshake):
                  self.hasPayload = True
                  print(struct.unpack("!8x20s20s", data[20:68]))
                  self.parseData(data[68:])
                  if(not self.payloadStillFetching and (self.state == State.Have or self.state == State.Bitfield)):
                         print self.payloadBit.bin
                         self.pieceList = self.pieceNum * [None]
                         self.sendInterested()
                  print "testrtttttttttttttttttttt"
                  print ";;;"
           else:
                  self.parseData(data)
                  #self.sendInterested()
                  #self.sendRequest()
                  if(not self.payloadStillFetching and (self.state == State.Have or self.state == State.Bitfield)):
                         print self.payloadBit.bin
                         self.pieceList = self.pieceNum * [None]
                         self.sendInterested()
                     
           #self.transport.loseConnection()
                  
class EchoFactory(protocol.ClientFactory):
        def __init__(self, message, bDict):
               self.message = message
               self.d = bDict
        def buildProtocol(self, addr):
               return EchoClient(self.message, self.d)

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
        print(left)
        event = "started"
        compact = 1

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
        ip = self.getIPPortList();
        self.sendToSinglePeer("127.0.0.1", 45030, handshake)
        #self.sendToSinglePeer(ip[0][0], ip[0][1], handshake)

    def sendToSinglePeer(self, ip, port, message):
        reactor.connectTCP(ip, port, EchoFactory(message, self.bDict))
        reactor.run()

def main(filename):
    file = open(filename, 'rb')
    benDict = bdecode(file.read())
    peerID = "-IO0001-012345678901"
    client = BitClient(benDict, peerID)

    client.sendHandshake()
