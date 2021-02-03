from __future__ import print_function

#discord stuff
import discord

#ffxiv stuff
import xivapi

#google doc stuff
import datetime
from datetime import timedelta
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

#other stuff
import asyncio
import aiohttp
import time
import threading
import random

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

client = discord.Client()
commandPrefix = '$'

xivClient = None
xivClientReady = False
async def SeupFFXIV():
    global xivClient
    global xivClientReady
    xivkey = None
    with open('xivkey', 'r') as xivKeyFile:
        xivkey = xivKeyFile.readline()
    loop = asyncio.get_event_loop()
    session = aiohttp.ClientSession(loop=loop)
    xivClient = xivapi.Client(session=session, api_key=xivkey)
    xivClientReady = True

eqCalendarId = 'nujrnhog654g3v0m0ljmjbp790@group.calendar.google.com'
eqChannels = {}
mpaMsgs = {}
mpaSizes = {}
mpaLock = threading.Lock()
try:
    with open('eqchannels', 'r') as eqChannelsFile:
        for line in eqChannelsFile:
            channelPair = line.split()
            eqChannels[int(channelPair[0])] = channelPair[1]
except IOError:
    with open('eqchannels', 'w') as eqChannelsFile:
        eqChannelsFile.write('')

eqEtag = 'Smoke weed everyday'
try:
    with open('eqetag', 'r') as eqEtagFile:
        eqEtag = eqEtagFile.readline()
except IOError:
    with open('eqetag', 'w') as eqEtagFile:
        eqEtagFile.write(eqEtag)

async def BotEventLoop():
    await SeupFFXIV()

    global eqEtag
    # Update EQ Calendar in subscribed channels
    while True:
        if client.is_ready():
            newEqEtag = GetEventsEtag(eqCalendarId)
            if newEqEtag != eqEtag:
                eqEtag = newEqEtag
                with open('eqetag', 'w') as eqEtagFile:
                    eqEtagFile.write(eqEtag)
                toRemove = []
                for k, v in eqChannels.items():
                    channel = client.get_channel(k)
                    await channel.purge()
                    if channel != None:
                        await PrintEq(channel, v)
                    else:
                        toRemove.append(k)
                for i in toRemove:
                    del eqChannels[i]
                UpdateChannelsFile()
        await asyncio.sleep(60)

async def MPAEventLoop():
    while True:
        if client.is_ready():
            await UpdateMPAs()
        await asyncio.sleep(5)

client.loop.create_task(BotEventLoop())
client.loop.create_task(MPAEventLoop())

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
    if message.author.id == client.user.id:
        return
    if message.author.bot:
        return
    
    admin = False
    try:
        if message.channel.permissions_for(message.author).administrator:
            admin = True
    except:
        return

    if message.content.startswith(commandPrefix):
        content = message.content[1:].lower()

        if content.startswith('startmpa'):
            await StartMPA(message)
            return
        
        if content.startswith('help'):
            helpMessage = '**Available commands:**\n```' + \
                commandPrefix+'glams <first name> <surname> [world] - Prints out current glamours for a FFXIV character.  Pulls from Lodestone, which is pretty slow and only updates every 6 hours or so.\n' + \
                commandPrefix+'eqstart <timezone> - Subsribes the current channel for EQ updates\n' + \
                commandPrefix+'eq <timezone> - Prints out the upcoming EQs in whatever timezone\n' + \
                commandPrefix+'eqw - Prints out the upcoming EQs in US Best Coast time\n' + \
                commandPrefix+'eqe - Prints out the upcoming EQs in US East time\n' + \
                commandPrefix+'eqc - Prints out the upcoming EQs in US Central time\n' + \
                '```'
            await message.channel.send(helpMessage)
            return

        if content.startswith('clearetag') and admin:
            global eqEtag
            eqEtag = 'wellfuck'
            return
        
        if content.startswith('eqe') and admin:
            await PrintEq(message.channel, 'America/New_York')
            return

        if content.startswith('eqw') and admin:
            await PrintEq(message.channel, 'America/Los_Angeles')
            return

        if content.startswith('eqc') and admin:
            await PrintEq(message.channel, 'America/Chicago')
            return

        if content.startswith('eqstart') and admin:
            args = message.content.split()
            if message.channel.id in eqChannels:
                await message.channel.send("This channel is already subscribed to EQ calendar updates")
                return
            if len(args) > 1:
                eqChannels[message.channel.id] = args[1]
            else:
                eqChannels[message.channel.id] = 'GMT'
            UpdateChannelsFile()
            await message.channel.send("This channel is now subscribed to EQ calendar updates")
            return

        if content.startswith('eqstop') and admin:
            if message.channel.id in eqChannels:
                del eqChannels[message.channel.id]
                UpdateChannelsFile()
                await message.channel.send("This channel is no longer subscribed to EQ calendar updates")
            else:
                await message.channel.send("This channel is not subscribed")
            return

        if content.startswith('eq') and admin:
            args = message.content.split()
            if len(args) > 1:
                await PrintEq(message.channel, args[1])
            else:
                await PrintEq(message.channel, 'UTC')
            return

        if content.startswith('glams'):
            await PrintGlams(message)
            return

async def PrintEq(channel, tzReq):
    service = GetCalendarService()

    # Call the Calendar API
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    later = (datetime.datetime.utcnow() + timedelta(days=7)).isoformat() + 'Z'
    events_result = service.events().list(
        calendarId=eqCalendarId,
        timeZone=tzReq,
        timeMin=now,
        timeMax=later,
        singleEvents=True,
        orderBy='startTime').execute()
    events = events_result.get('items', [])

    strEvents = '**Upcoming events (' + tzReq +'):**\n```'
    maxLines = 20
    count = 0
    curMessage = 0
    maxMessages = 2
    if not events:
        strEvents = 'No upcoming events found.'
    else:
        for event in events:
            count = count + 1
            start = event['start'].get('dateTime', event['start'].get('date'))
            try:
                date = datetime.datetime.strptime(start, '%Y-%m-%dT%H:%M:%S%z')
            except:
                try:
                    date = datetime.datetime.strptime(start, '%Y-%m-%d')
                except:
                    continue

            strEvents += date.strftime('%b %d %I:%M %p') + ' - ' + event['summary'] + '\n'
            if count >= maxLines:
                strEvents += '```'
                if curMessage < maxMessages:
                    await channel.send(strEvents)
                    curMessage = curMessage + 1
                count = 0
                strEvents = '```'
    if count > 0:
        strEvents += '```'
        if curMessage < maxMessages:
            await channel.send(strEvents)
    return

def GetEventsEtag(calendarId):
    service = GetCalendarService()

    # Call the Calendar API
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    later = (datetime.datetime.utcnow() + timedelta(days=7)).isoformat() + 'Z'
    events_result = service.events().list(
        calendarId=eqCalendarId,
        timeMin=now,
        timeMax=later,
        singleEvents=True,
        orderBy='startTime').execute()
    events = events_result.get('items', [])
    eventStr = ""
    for event in events:
        eventStr = eventStr + event['id']
    return eventStr+str(len(events))

def GetCalendarService():
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return build('calendar', 'v3', credentials=creds)

def UpdateChannelsFile():
    toWrite = ''
    for k, v in eqChannels.items():
        toWrite = toWrite + str(k) + ' ' + str(v) + '\n'
    toWrite = toWrite[:-1]
    with open('eqchannels', 'w') as eqChannelsFile:
        eqChannelsFile.write(toWrite)

async def PrintGlams(message):
    if not xivClientReady:
        return
    args = message.content.split()
    if len(args) < 3:
        await message.channel.send('Usage: ' + commandPrefix + 'glams forename surname [world]')
        return
    if len(args) == 3:
        character = await xivClient.character_search(
            world='',
            forename=args[1],
            surname=args[2])
        if (len(character['Results']) > 1):
            resultsString = 'Found characters:'
            for result in character['Results']:
                resultsString = resultsString + '\n' + \
                    result['Name'] + '@' + result['Server']
            await message.channel.send(resultsString)
            return
        await PrintCharacter(message, character, args[1] + ' ' + args[2])
    if len(args) == 4:
        character = await xivClient.character_search(
            world=args[3],
            forename=args[1],
            surname=args[2])
        await PrintCharacter(message, character, args[1] + ' ' + args[2])
    return

async def PrintCharacter(message, character, fullName):
    if (len(character['Results']) > 0):
        trueResult = character['Results'][0]
        for result in character['Results']:
            if result['Name'] == fullName:
                trueResult = result
                break
        profile = await xivClient.character_by_id(
            lodestone_id=trueResult['ID'])
        name = profile['Character']['Name']
        server = profile['Character']['Server']
        portrait = profile['Character']['Portrait']

        if not 'MainHand' in profile['Character']['GearSet']['Gear']:
            mhName = "None"
        else:
            mhId = profile['Character']['GearSet']['Gear']['MainHand']['Mirage']
            if mhId == None:
                mhId = profile['Character']['GearSet']['Gear']['MainHand']['ID']
            mhName = await GetXIVItemName(mhId)

        if not 'OffHand' in profile['Character']['GearSet']['Gear']:
            ohName = "None"
        else:
            ohId = profile['Character']['GearSet']['Gear']['OffHand']['Mirage']
            if ohId == None:
                ohId = profile['Character']['GearSet']['Gear']['OffHand']['ID']
            ohName = await GetXIVItemName(ohId)

        if not 'Head' in profile['Character']['GearSet']['Gear']:
            headName = "None"
        else:
            headId = profile['Character']['GearSet']['Gear']['Head']['Mirage']
            if headId == None:
                headId = profile['Character']['GearSet']['Gear']['Head']['ID']
            headName = await GetXIVItemName(headId)

        if not 'Body' in profile['Character']['GearSet']['Gear']:
            bodyName = "None"
        else:
            bodyId = profile['Character']['GearSet']['Gear']['Body']['Mirage']
            if bodyId == None:
                bodyId = profile['Character']['GearSet']['Gear']['Body']['ID']
            bodyName = await GetXIVItemName(bodyId)

        if not 'Hands' in profile['Character']['GearSet']['Gear']:
            handsName = "None"
        else:
            handsId = profile['Character']['GearSet']['Gear']['Hands']['Mirage']
            if handsId == None:
                handsId = profile['Character']['GearSet']['Gear']['Hands']['ID']
            handsName = await GetXIVItemName(handsId)

        if not 'Legs' in profile['Character']['GearSet']['Gear']:
            legsName = "None"
        else:
            legsId = profile['Character']['GearSet']['Gear']['Legs']['Mirage']
            if legsId == None:
                legsId = profile['Character']['GearSet']['Gear']['Legs']['ID']
            legsName = await GetXIVItemName(legsId)

        if not 'Feet' in profile['Character']['GearSet']['Gear']:
            feetName = "None"
        else:
            feetId = profile['Character']['GearSet']['Gear']['Feet']['Mirage']
            if feetId == None:
                feetId = profile['Character']['GearSet']['Gear']['Feet']['ID']
            feetName = await GetXIVItemName(feetId)

        messageBody = '**' + name + '@' + server + '**```' + \
            '\nMain Hand: ' + mhName + \
            '\nOff Hand: ' + ohName + \
            '\nHead: ' + headName + \
            '\nBody: ' + bodyName + \
            '\nHands: ' + handsName + \
            '\nLegs: ' + legsName + \
            '\nFeet: ' + feetName + \
            '```'

        await message.channel.send(portrait)
        await message.channel.send(messageBody)
    return

async def GetXIVItemName(itemID):
    if not xivClientReady:
        return
    item = await xivClient.index_by_id(
        index='Item',
        content_id=itemID,
        columns=['Name'],
        language='en')
    return item['Name']

@client.event
async def on_reaction_add(reaction, user):
    global mpaMsgs
    global mpaLock
    mpaLock.acquire()
    for message in mpaMsgs:
        if message.id == reaction.message.id:
            messageDict = mpaMsgs[message]
            if user in messageDict:
                messageDict[user].append(reaction)
            else:
                messageDict[user] = []
                messageDict[user].append(reaction)
            mpaMsgs[message] = messageDict
            break
    mpaLock.release()
    return

@client.event
async def on_reaction_remove(reaction, user):
    global mpaMsgs
    global mpaLock
    mpaLock.acquire()
    found = False
    for message in mpaMsgs:
        if message.id == reaction.message.id:
            for foundUser in mpaMsgs[message]:
                if foundUser.id == user.id:
                    for foundReaction in mpaMsgs[message][foundUser]:
                        if str(reaction.emoji) == str(foundReaction.emoji):
                            mpaMsgs[message][foundUser].remove(foundReaction)
                            found = True
                            break
                if not mpaMsgs[message][foundUser]:
                    mpaMsgs[message].pop(user)
                if found:
                    break
        if found:
            break
    mpaLock.release()
    return

async def StartMPA(message):
    global mpaMsgs
    global mpaSizes
    global mpaLock
    
    args = message.content.split()
    try:
        if int(args[1])%4 != 0:
            return
    except:
        return
    body = "Setting everything up, please wait..."
    newMsg = await message.channel.send(body)

    await newMsg.add_reaction("<:Wave:731073709661749258>")
    await newMsg.add_reaction("<:Class_Techer:789166122669703200>")
    await newMsg.add_reaction("<:Class_Ranger:789166122720165909>")
    await newMsg.add_reaction("<:Class_Hunter:789166122817421312>")
    await newMsg.add_reaction("<:Class_Force:789166122502717466>")
    await newMsg.add_reaction("<:Class_Fighter:789166122799726592>")
    await newMsg.add_reaction("<:Class_Gunner:789166122745856030>")
    await newMsg.add_reaction("<:Class_Braver:789165133086851082>")
    await newMsg.add_reaction("<:Class_Bouncer:789166122795663430>")
    await newMsg.add_reaction("<:Class_Summoner:789165132903088205>")
    await newMsg.add_reaction("<:Class_Hero:788564090774749195>")
    await newMsg.add_reaction("<:Class_Phantom:789166122816634931>")
    await newMsg.add_reaction("<:Class_Etoile:724042850307670016>")
    await newMsg.add_reaction("<:Class_Luster:788563161020104766>")
    await newMsg.add_reaction("\N{LOCK}")

    body = str(int(args[1])) + "-man MPA commencing, awaiting operatives!\n\nSelect your class below!  Additionally, select <:Wave:731073709661749258> to enlist as a Field Officer!"
    await newMsg.edit(content=body)

    mpaLock.acquire()
    mpaMsgs[newMsg] = {}
    mpaSizes[newMsg] = int(args[1])
    mpaLock.release()
    return

async def UpdateMPAs():
    global mpaMsgs
    global mpaLock
    mpaLock.acquire()
    mpaMsgsCopy = mpaMsgs.copy()
    mpaLock.release()
    for message in mpaMsgsCopy:
        try:
            fetchedMessage = await message.channel.fetch_message(message.id)
        except Exception as e:
            mpaLock.acquire()
            mpaMsgs.pop(message)
            mpaLock.release()
            break
        await UpdateMPA(message, fetchedMessage)
    return

async def UpdateMPA(message, fetchedMessage):
    global mpaMsgs
    global mpaSizes
    global mpaLock
    mpaLock.acquire()
    originalMsg = message.content
    users = mpaMsgs[message].copy()
    mpaSize = int(mpaSizes[message])
    partiesPerMPA = int(mpaSize / 4)
    mpaLock.release()

    # Get the total arks count
    arksCount = 0
    for user in users:
        numSlots = 0
        for reaction in users[user]:
            if IsClass(reaction):
                arksCount = arksCount + 1
                numSlots = numSlots + 1
            if numSlots >= 4:
                break

    numMPAs = int(1 + ((arksCount-1) / mpaSize))
    mpaFull = arksCount & mpaSize == 0
    lastMPARequiringLeaders = numMPAs
    if not mpaFull:
        lastMPARequiringLeaders = numMPAs - 1
    if lastMPARequiringLeaders < 1:
        lastMPARequiringLeaders = 1

    mpa = {}
    for x in range(numMPAs):
        mpa[x] = {}
        for y in range(partiesPerMPA):
            mpa[x][y] = {"te":0, "ra":0, "leader":False, "members":[]}

    # Start with people who are bringing guests, they are forced to lead parties
    while True:
        found = False
        for k, v in users.items():
            numSlots = 0
            willLead = False
            techers = 0
            rangers = 0
            name = k.display_name
            nameList = []
            for reaction in v:
                if IsClass(reaction):
                    if numSlots < 1:
                        nameList.append(str(reaction.emoji) + " " + name)
                    else:
                        nameList.append(str(reaction.emoji) + " " + name + "\'s guest")
                    numSlots = numSlots + 1
                if IsTecher(reaction):
                    techers = techers + 1
                if IsRanger(reaction):
                    rangers = rangers + 1
                if numSlots > 3:
                    break
            if numSlots > 1:
                willLead = True
            # Look for parties that need leaders
            if willLead:
                for x in range(lastMPARequiringLeaders):
                    for y in range(partiesPerMPA):
                        if not mpa[x][y]["leader"]:
                            found = True
                            mpa[x][y]["members"] = nameList
                            mpa[x][y]["leader"] = True
                            mpa[x][y]["te"] = techers
                            mpa[x][y]["ra"] = rangers
                            users.pop(k)
                            break
                    if found:
                        break
                # no empty parties, see if we can fill
                if not found:
                    for x in range(numMPAs):
                        for y in range(partiesPerMPA):
                            if len(mpa[x][y]["members"]) <= 4 - numSlots:
                                found = True
                                for appendName in nameList:
                                    mpa[x][y]["members"].append(appendName)
                                mpa[x][y]["te"] = mpa[x][y]["te"] + techers
                                mpa[x][y]["ra"] = mpa[x][y]["ra"] + rangers
                                users.pop(k)
                                break
                        if found:
                            break
                # there isn't room either, so they're getting split up I guess
            if found:
                break
        if not found:
            break

    # Find other leaders
    while True:
        found = False
        for k, v in users.items():
            willLead = False
            techers = 0
            rangers = 0
            name = k.display_name
            foundClass = False
            for reaction in v:
                if IsClass(reaction):
                    name = str(reaction.emoji) + " " + name
                    foundClass = True
                if IsTecher(reaction):
                    techers = techers + 1
                if IsRanger(reaction):
                    rangers = rangers + 1
                if IsLeader(reaction):
                    willLead = True
            # Look for parties that need leaders
            if willLead and foundClass:
                for x in range(lastMPARequiringLeaders):
                    for y in range(partiesPerMPA):
                        if not mpa[x][y]["leader"]:
                            found = True
                            mpa[x][y]["members"].append(name)
                            mpa[x][y]["leader"] = True
                            mpa[x][y]["te"] = techers
                            mpa[x][y]["ra"] = rangers
                            users.pop(k)
                            break
                    if found:
                        break
            #if we didn't find a party that needs a leader, treat this like a normal player below
            if found:
                break
        if not found:
            break

    # Fill in the rest
    remainingUsers = []
    for k, v in users.items():
        name = k.display_name
        numSlots = 0
        for reaction in v:
            if IsClass(reaction):
                if numSlots < 1:
                    remainingUsers.append(str(reaction.emoji) + " " + name)
                else:
                    remainingUsers.append(str(reaction.emoji) + " " + name + "\'s guest")
                numSlots = numSlots + 1
                if numSlots >= 4:
                    break

    while remainingUsers:
        found = False
        for normalUser in remainingUsers:
            for x in range(numMPAs):
                for y in range(partiesPerMPA):
                    if len(mpa[x][y]["members"]) < 4:
                        found = True
                        mpa[x][y]["members"].append(normalUser)
                        remainingUsers.remove(normalUser)
                        break
                if found:
                    break
            if found:
                break
        if not found:
            break

    # Edit the message
    messageContent = ""
    for x in range(numMPAs):
        messageContent = messageContent + "**MPA " + str(x + 1) + " (Password: " + str(GetPassword(message, x)) + ")**\n"
        for y in range(partiesPerMPA):
            messageContent = messageContent + "Party " + str(y + 1) + ": "
            if len(mpa[x][y]["members"]) > 0:
                messageContent = messageContent + mpa[x][y]["members"][0] + " / "
            else:
                messageContent = messageContent + "*empty*" + " / "
            if len(mpa[x][y]["members"]) > 1:
                messageContent = messageContent + mpa[x][y]["members"][1] + " / "
            else:
                messageContent = messageContent + "*empty*" + " / "
            if len(mpa[x][y]["members"]) > 2:
                messageContent = messageContent + mpa[x][y]["members"][2] + " / "
            else:
                messageContent = messageContent + "*empty*" + " / "
            if len(mpa[x][y]["members"]) > 3:
                messageContent = messageContent + mpa[x][y]["members"][3] + "\n\n"
            else:
                messageContent = messageContent + "*empty*\n\n"

    if not messageContent:
        messageContent = str(mpaSize) + "-man MPA commencing, awaiting operatives!\n\nSelect your class below!  Additionally, select <:Wave:731073709661749258> to enlist as a Field Officer!"
    else:
        messageContent = messageContent + "Select your class below!  Additionally, select <:Wave:731073709661749258> to enlist as a Field Officer!"

    locked = False
    for reaction in fetchedMessage.reactions:
        if IsLock(reaction) and reaction.count > 1:
            locked = True
            break

    if locked:
        if "This MPA is locked! I'm still tracking reactions, though, unlock me to continue!" not in originalMsg:
            lockedContent = originalMsg + "\n\nThis MPA is locked! I'm still tracking reactions, though, unlock me to continue!"
        else:
            lockedContent = originalMsg
        if message.content != lockedContent:
            await message.edit(content=lockedContent)
    else:
        if message.content != messageContent:
            await message.edit(content=messageContent)
    return

def IsClass(reaction):
    reactionStr = str(reaction)
    classList = [
        "<:Class_Techer:789166122669703200>",
        "<:Class_Ranger:789166122720165909>",
        "<:Class_Hunter:789166122817421312>",
        "<:Class_Force:789166122502717466>",
        "<:Class_Fighter:789166122799726592>",
        "<:Class_Gunner:789166122745856030>",
        "<:Class_Braver:789165133086851082>",
        "<:Class_Bouncer:789166122795663430>",
        "<:Class_Summoner:789165132903088205>",
        "<:Class_Hero:788564090774749195>",
        "<:Class_Phantom:789166122816634931>",
        "<:Class_Etoile:724042850307670016>",
        "<:Class_Luster:788563161020104766>"]
    return reactionStr in classList

def IsLeader(reaction):
    reactionStr = str(reaction)
    leaderList = [
        "<:Wave:731073709661749258>"]
    return reactionStr in leaderList

def IsTecher(reaction):
    reactionStr = str(reaction)
    classList = [
        "<:Class_Techer:789166122669703200>"]
    return reactionStr in classList

def IsRanger(reaction):
    reactionStr = str(reaction)
    classList = [
        "<:Class_Ranger:789166122720165909>"]
    return reactionStr in classList

def IsLock(reaction):
    reactionStr = str(reaction)
    lockList = [
        "\N{LOCK}"]
    return reactionStr in lockList

def GetPassword(message, x):
    random.seed(message.id+x)
    return random.randint(1, 999)

tokenFile = open("bottoken", 'r')
client.run(tokenFile.readline())
tokenFile.close()
