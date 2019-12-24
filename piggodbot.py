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

commandPrefix = '$'

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith(commandPrefix):
        content = message.content[1:]

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
            await PrintEq(message, 'America/New_York')
            return

        if content.startswith('eqw'):
            await PrintEq(message, 'America/Los_Angeles')
            return

        if content.startswith('eqc'):
            await PrintEq(message, 'America/Chicago')
            return

        if content.startswith('eq'):
            args = message.content.split()
            if len(args) > 1:
                await PrintEq(message, args[1])
            else:
                await PrintEq(message, 'UTC')
            return

    if 'techer' in message.content.lower():
        await message.add_reaction('<:Techer:645433477088411680>')
        await message.add_reaction('<:Force:645433476979621889>')
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
    else:
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