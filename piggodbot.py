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
                    channel.purge()
                    if channel != None:
                        await PrintEq(channel, v)
                    else:
                        toRemove.append(k)
                for i in toRemove:
                    del eqChannels[i]
                UpdateChannelsFile()
        await asyncio.sleep(60)

client.loop.create_task(BotEventLoop())

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith(commandPrefix):
        content = message.content[1:].lower()

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

        if content.startswith('clearetag'):
            eqEtag = 'wellfuck'
            return
        
        if content.startswith('eqe'):
            await PrintEq(message.channel, 'America/New_York')
            return

        if content.startswith('eqw'):
            await PrintEq(message.channel, 'America/Los_Angeles')
            return

        if content.startswith('eqc'):
            await PrintEq(message.channel, 'America/Chicago')
            return

        if content.startswith('eqstart'):
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

        if content.startswith('eqstop'):
            if message.channel.id in eqChannels:
                del eqChannels[message.channel.id]
                UpdateChannelsFile()
                await message.channel.send("This channel is no longer subscribed to EQ calendar updates")
            else:
                await message.channel.send("This channel is not subscribed")
            return

        if content.startswith('eq'):
            args = message.content.split()
            if len(args) > 1:
                await PrintEq(message.channel, args[1])
            else:
                await PrintEq(message.channel, 'UTC')
            return

        if content.startswith('glams'):
            await PrintGlams(message)
            return

    if 'techer' in message.content.lower() or 'techter' in message.content.lower():
        await message.add_reaction('<:Techer:645433477088411680>')
        await message.add_reaction('<:Force:645433476979621889>')
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

async def GetXIVItemName(itemID):
    if not xivClientReady:
        return
    item = await xivClient.index_by_id(
        index='Item',
        content_id=itemID,
        columns=['Name'],
        language='en')
    return item['Name']

tokenFile = open("bottoken", 'r')
client.run(tokenFile.readline())
tokenFile.close()
