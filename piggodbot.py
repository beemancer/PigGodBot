from __future__ import print_function

#discord stuff
import discord

#google doc stuff
import datetime
import pickle
import os.path
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

#other stuff
import asyncio
import time
import threading

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

client = discord.Client()
commandPrefix = '$'
eqCalendarId = 'pso2emgquest@gmail.com'

eqChannels = {}
try:
    with open('eqchannels', 'r') as eqEtagFile:
        for line in eqEtagFile:
            channelPair = line.split()
            eqChannels[int(channelPair[0])] = channelPair[1]
except:
    print('aw shit')

eqEtag = 'Smoke weed everyday'
try:
    with open('eqetag', 'r') as eqEtagFile:
        eqEtag = eqEtagFile.readline()
except IOError:
    with open('eqetag', 'w') as eqEtagFile:
        eqEtagFile.write(eqEtag)

async def CheckEQCalendar():
    global eqEtag
    while True:
        newEqEtag = GetEventsEtag(eqCalendarId)
        if newEqEtag != eqEtag:
            eqEtag = newEqEtag
            with open('eqetag', 'w') as eqEtagFile:
                eqEtagFile.write(eqEtag)
            for k, v in eqChannels.items():
                channel = client.get_channel(k)
                await PrintEq(channel, v)
        await asyncio.sleep(60)

client.loop.create_task(CheckEQCalendar())

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
                commandPrefix+'eq <timezone> - Prints out the upcoming EQs in whatever timezone\n' + \
                commandPrefix+'eqw - Prints out the upcoming EQs in US Best Coast time\n' + \
                commandPrefix+'eqe - Prints out the upcoming EQs in US East time\n' + \
                commandPrefix+'eqc - Prints out the upcoming EQs in US Central time\n' + \
                '```'
            await message.channel.send(helpMessage)
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

    if 'techer' in message.content.lower():
        await message.add_reaction('<:Techer:645433477088411680>')
        await message.add_reaction('<:Force:645433476979621889>')
        return

async def PrintEq(channel, tzReq):
    service = GetCalendarService()

    # Call the Calendar API
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    events_result = service.events().list(
        calendarId=eqCalendarId,
        timeZone=tzReq,
        timeMin=now,
        singleEvents=True,
        orderBy='startTime').execute()
    events = events_result.get('items', [])

    strEvents = '**Upcoming events (' + tzReq +'):**\n```'
    if not events:
        strEvents = 'No upcoming events found.'
    else:
        maxLines = 20
        count = 0
        for event in events:
            count = count + 1
            start = event['start'].get('dateTime', event['start'].get('date'))
            date = datetime.datetime.strptime(start, '%Y-%m-%dT%H:%M:%S%z')
            strEvents += date.strftime('%b %d %H:%M') + ' - ' + event['summary'] + '\n'
            if count >= maxLines:
                strEvents += '```'
                await channel.send(strEvents)
                count = 0
                strEvents = '```'
    if count > 0:
        strEvents += '```'
        await channel.send(strEvents)
    return

def GetEventsEtag(calendarId):
    service = GetCalendarService()

    # Call the Calendar API
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    events_result = service.events().list(
        calendarId=eqCalendarId,
        timeMin=now,
        singleEvents=True,
        orderBy='startTime').execute()
    events = events_result.get('items', [])
    return events_result.get('etag')+str(len(events))

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

tokenFile = open("bottoken", 'r')
client.run(tokenFile.readline())
tokenFile.close()