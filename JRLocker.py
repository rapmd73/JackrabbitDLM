#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Jackrabbit DLM
# 2021 Copyright © Robert APM Darin
# All rights reserved unconditionally.

import sys
sys.path.append('/home/JackrabbitDLM')
import os
import datetime
import time
import random
import socket
import json

# Reusable file locks
#
# fw=Locker(filename)
# fw.Lock()
# ( do somwething )
# fw.Unlock()

# { "ID":"DEADBWEEF", "FileName":"testData", "Action":"Lock", "Expire":"300" }

class Locker:
    # Initialize the file name
    def __init__(self,filename,Retry=7,RetrySleep=0.1,Timeout=300,ID=None,Host='',Port=37373):
        self.ulResp=['badpayload','locked','unlocked','notowner','notfound']

        if ID==None:
            self.ID=self.GetID()
        else:
            self.ID=ID
        self.filename=filename
        self.retryLimit=Retry
        self.retrysleep=RetrySleep
        self.timeout=Timeout
        self.port=Port
        self.host=Host

    # Generate an ID String

    def GetID(self):
        letters="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        llen=len(letters)

        pw=""
        oc=""

        random.seed(time.time())
        for i in range(37):
            done=False
            while not done:
                for z in range(random.randrange(73,237)):
                    c=random.randrange(llen)
                if pw=="" or (len(pw)>0 and letters[c]!=oc):
                    done=True
            oc=letters[c]
            pw+=oc
        return pw

    # Contact the Locker Server and WAIT for response. NOT thread safe.

    def Talker(self,msg,casefold=True):
        try:
            ls=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ls.settimeout(self.timeout)
            ls.connect((self.host, self.port))
            sfn=ls.makefile('rw')
            sfn.write(msg)
            sfn.flush()
            buf=None
            while buf==None:
                buf=sfn.readline()
            ls.close()
            if len(buf)!=0:
                if casefold==True:
                    return buf.lower().strip()
                else:
                    return buf.strip()
            else:
                return None
        except Exception as err:
            print("Error",err)
            return None

    # Contact Lock server

    def Retry(self,action,expire,casefold=True):
        outbuf='{ '+f'"ID":"{self.ID}", "FileName":"{self.filename}", "Action":"{action}", "Expire":"{expire}"'+' }\n'

        retry=0
        done=False
        while not done:
            buf=self.Talker(outbuf,casefold)
            if buf==None:
                if retry>self.retryLimit:
                    return 'failure'
                retry+=1
                time.sleep(self.retrysleep)
            else:
                if len(buf)!=0:
                    # Received JSON, brak done and get status
                    try:
                        bData=json.loads(buf)
                        s='Status'
                        if casefold:
                            s='status'
                        buf=bData[s]
                    except:
                        buf=None
                    if casefold==True and buf!=None:
                        buf=buf.lower()
                    if buf!=None and buf in self.ulResp:
                        done=True
                    else:
                        time.sleep(self.retrysleep)
                else:
                    time.sleep(self.retrysleep)
        return buf

    def RetryData(self,action,expire,data):
        outbuf='{ '+f'"ID":"{self.ID}", "FileName":"{self.filename}", "Action":"{action}", "Expire":"{expire}", "DataStore":"{data}"'+' }\n'

        retry=0
        done=False
        while not done:
            buf=self.Talker(outbuf,casefold=False)
            if buf==None:
                if retry>self.retryLimit:
                    return 'failure'
                retry+=1
                time.sleep(self.retrysleep)
            else:
                if len(buf)!=0:
                    done=True
                else:
                    time.sleep(self.retrysleep)
        return buf

    # Lock the file

    def Lock(self,expire=300):
        return self.Retry("Lock",expire,casefold=True)

    # Check if the item is locked. Will aquire if not. Single pass, no loop

    def IsLocked(self,expire=300):
        outbuf='{ '+f'"ID":"{self.ID}", "FileName":"{self.filename}", "Action":"Lock", "Expire":"{expire}"'+' }\n'
        buf=self.Talker(outbuf,casefold=True)
        if buf==None:
            return 'failure'
        bData=json.loads(buf)
        buf=bData['status']
        return buf

    # Unlock the file

    def Unlock(self):
        return self.Retry("Unlock",0)

    def Get(self):
        return self.RetryData("Get",0,None)

    def Put(self,expire,data):
        return self.RetryData("Put",expire,data)

    def Erase(self):
        return self.RetryData("Erase",0,None)

