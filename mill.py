#!/usr/bin/env python
# use Phidget analog input with vibration sensor to detect when the Othermill is milling.

# send push notifications when the run status changes

import requests # simple HTTP lib

PUSH_TOKEN=None
PUSH_USER_TOKEN=None

if PUSH_TOKEN is None: 
    import config
    PUSH_TOKEN=config.PUSH_TOKEN
    PUSH_USER_TOKEN=config.PUSH_USER_TOKEN
    
APP_NAME = "OtherMill"
ENABLE_PUSH = True
# phidget input numbers
VIB_DIGITAL = 7
VIB_ANALOG = 0

DEBUG_IO=False # print each event

MILL_STOP_TIME = 10 #30 # alert after this. wait awhile in case its just a temporary pause
MILL_START_TIME = 3 # must be vibrating this long to count as started
MILL_START_TIMEOUT = 1 # must get consistent vibration when starting to move


def send_push_notification(msg,ok=True ):
    if not ENABLE_PUSH:
        print "PUSH disabled: '%s'"%msg
        return
        
    if PUSH_TOKEN is None or PUSH_USER_TOKEN is None:
        print "! No PUSH tokens configured"
        return 
    try:
        print "PUSH: '%s'"%msg
        title = "%s %s"%(APP_NAME,"OK" if ok else "!WARN!")
        r=requests.post("https://api.pushover.net/1/messages.json",{
          "token":PUSH_TOKEN,
          "user": PUSH_USER_TOKEN,
          "title":title,
          "message":msg,
          "priority": 0 if ok else 1, # RED if 1
        })
        print r.status_code
    except Exception as e:
        print "Could not send push notification: ",e
        
#Basic imports
from ctypes import *
import sys
import random
import time
#Phidget specific imports
from Phidgets.PhidgetException import PhidgetErrorCodes, PhidgetException
from Phidgets.Events.Events import AttachEventArgs, DetachEventArgs, ErrorEventArgs, InputChangeEventArgs, OutputChangeEventArgs, SensorChangeEventArgs
from Phidgets.Devices.InterfaceKit import InterfaceKit

#Create an interfacekit object
try:
    interfaceKit = InterfaceKit()
except RuntimeError as e:
    print("Runtime Exception: %s" % e.details)
    print("Exiting....")
    exit(1)


S_STOPPED=0
S_PRE_MOVE=1 # started moving, make sure its for real
S_MOVING=2

vib={
    "state":S_STOPPED,
    "lastDigital":False,
    "lastAnalog":0,
    "updateTime":0, 
    "stopTime":0,
    "startTime":0,
       
}


def isMoving():
    return vib["state"] == S_MOVING
    
def isStopped():
    return vib["state"] == S_STOPPED
    
def isStartingToMove():
    return vib["state"] == S_PRE_MOVE

def setStopped():
    vib["stopTime"]=time.time()  
    vib["state"]=S_STOPPED     
def setStarted():
    vib["state"] = S_PRE_MOVE         
    vib["startTime"]=time.time() 

def setMoving():
    s["state"] = S_MOVING       
    
def vibrationUpdate(digital, analog):
    global vib
    dt = time.time()-vib["updateTime"]
    updated = False
    if digital is not None:
       vib["lastDigital"]=digital
        
    if analog is not None: # action on the analog input is more likely than digital
        vib["lastAnalog"]=analog
        stopCount=time.time()
        updated = True

    if updated:
        print "VIB:dt=%2.2f %d %d"%(dt,vib["lastDigital"],vib["lastAnalog"])
        vib["updateTime"]=time.time()

    
   
    if isStopped():
        print "Started moving - wait to see if this is real"
        setStarted()
    
            
    if isStartingToMove() and time.time() - vib["moveStart"] > MILL_START_TIME:
        print "Moving consistently"
        pausetime = time.time()-vib["stopTime"]
        mstr = ("%2.2f seconds"%pausetime) if pausetime < 60*60 else "awhile"
        send_push_notification("Mill started moving after %s"%mstr)
        setMoving()
    else:
        print "MOVING"
        
    
########################################

#Information Display Function
def displayDeviceInfo():
    print("|------------|----------------------------------|--------------|------------|")
    print("|- Attached -|-              Type              -|- Serial No. -|-  Version -|")
    print("|------------|----------------------------------|--------------|------------|")
    print("|- %8s -|- %30s -|- %10d -|- %8d -|" % (interfaceKit.isAttached(), interfaceKit.getDeviceName(), interfaceKit.getSerialNum(), interfaceKit.getDeviceVersion()))
    print("|------------|----------------------------------|--------------|------------|")
    print("Number of Digital Inputs: %i" % (interfaceKit.getInputCount()))
    print("Number of Digital Outputs: %i" % (interfaceKit.getOutputCount()))
    print("Number of Sensor Inputs: %i" % (interfaceKit.getSensorCount()))

#Event Handler Callback Functions
def interfaceKitAttached(e):
    attached = e.device
    print("InterfaceKit %i Attached!" % (attached.getSerialNum()))

def interfaceKitDetached(e):
    detached = e.device
    print("InterfaceKit %i Detached!" % (detached.getSerialNum()))

def interfaceKitError(e):
    try:
        source = e.device
        print("InterfaceKit %i: Phidget Error %i: %s" % (source.getSerialNum(), e.eCode, e.description))
    except PhidgetException as e:
        print("Phidget Exception %i: %s" % (e.code, e.details))

def interfaceKitInputChanged(e):
    source = e.device
   # sendDigitalInputChange(source,e.index,e.state)
    if(DEBUG_IO):
        print("InterfaceKit %i: Input %i: %s" % (source.getSerialNum(), e.index, e.state))
    if e.index == VIB_DIGITAL:
        vibrationUpdate(e.state,None)
        
def interfaceKitSensorChanged(e):
    source = e.device
    if(DEBUG_IO):
        print("InterfaceKit %i: Sensor %i: %i" % (source.getSerialNum(), e.index, e.value))
    if e.index == VIB_ANALOG:
        vibrationUpdate(None,e.value)

def interfaceKitOutputChanged(e):
    source = e.device
    if(DEBUG_IO):
        print("InterfaceKit %i: Output %i: %s" % (source.getSerialNum(), e.index, e.state))

#Main Program Code
try:
    interfaceKit.setOnAttachHandler(interfaceKitAttached)
    interfaceKit.setOnDetachHandler(interfaceKitDetached)
    interfaceKit.setOnErrorhandler(interfaceKitError)
    interfaceKit.setOnInputChangeHandler(interfaceKitInputChanged)
    #interfaceKit.setOnOutputChangeHandler(interfaceKitOutputChanged)
    interfaceKit.setOnSensorChangeHandler(interfaceKitSensorChanged)
except PhidgetException as e:
    print("Phidget Exception %i: %s" % (e.code, e.details))
    print("Exiting....")
    exit(1)


def fail(exit_on_fail):
    if exit_on_fail:
        print "Exiting..."
    else:
        print("Continue without input device")
        
def connectToPhidget(timeout=5000, exit_on_fail = False):
    print("Opening phidget object....")
    while True:
        try:
            interfaceKit.openPhidget()
            print("Waiting %d seconds for attach...."%(timeout/1000))
            interfaceKit.waitForAttach(timeout)
            displayDeviceInfo()
            break
            
        except PhidgetException as e:
            print("Phidget Exception %i: %s" % (e.code, e.details))
            #fail(exit_on_fail)
            interfaceKit.closePhidget()
        # try again...
        time.sleep(1)


connectToPhidget() # always connect when file is imported

if __name__ == '__main__':
        # main()
    
    send_push_notification("%s script START"%__file__)
    print("Listening for inputs ....")
   
    while True:
        
        dt = time.time()-vib["updateTime"] # time since last sensor update (vibration detected)
        if isStartingToMove() and dt > MILL_START_TIMEOUT:
            print "False alarm - not moving consistently"
            setStopped() # no push
        elif isMoving() and dt > MILL_STOP_TIME: # been stopped for awhile
            print "STOPPED ???"
            runtime = time.time()-vib["startTime"]
            if runtime < 60:
                rstr="%2.2f seconds"%runtime
            elif runtime < 3*60*60:
                rstr="%2.2f minutes"%(runtime/60.0)
            else:
                rstr="%2.2f hours"%(runtime/3600.0)
                
            send_push_notification("Mill stopped %2.2f  runtime %s"%(dt,rstr))
            setStopped()
            
        time.sleep(0.5)
    print("Closing...")

    try:
        interfaceKit.closePhidget()
    except PhidgetException as e:
        print("(main) Phidget Exception %i: %s" % (e.code, e.details))
        print("Exiting....")
        exit(1)
        
    send_push_notification("%s script STOPPED"%__file__,ok=False) 




