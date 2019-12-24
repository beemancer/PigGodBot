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

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

client = discord.Client()

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('$help'):
        await message.channel.send("The only commands are $eq <timezone>, $eqe, $eqw, and $eqc, how much help could you need?")
        return

    if message.content.startswith('$eqe'):
        await PrintEq(message, 'America/New_York')
        return

    if message.content.startswith('$eqw'):
        await PrintEq(message, 'America/Los_Angeles')
        return

    if message.content.startswith('$eqc'):
        await PrintEq(message, 'America/Chicago')
        return

    if message.content.startswith('$eq '):
        args = message.content.split()
        await PrintEq(message, args[1])
        return

async def PrintEq(message, tzReq):
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

    service = build('calendar', 'v3', credentials=creds)

    # Call the Calendar API
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    events_result = service.events().list(
        calendarId='pso2emgquest@gmail.com',
        timeZone=tzReq,
        timeMin=now,
        singleEvents=True,
        orderBy='startTime').execute()
    events = events_result.get('items', [])

    strEvents = '**Upcoming events (' + tzReq +'):**\n```'
    if not events:
        strEvents = 'No upcoming events found.'
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        date = datetime.datetime.strptime(start, '%Y-%m-%dT%H:%M:%S%z')
        strEvents += date.strftime('%b %d %H:%M') + ' - ' + event['summary'] + '\n'
    strEvents += '```'
    await message.channel.send(strEvents)
    return

tokenFile = open("bottoken", 'r')
client.run(tokenFile.readline())
tokenFile.close()