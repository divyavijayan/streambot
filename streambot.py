import os
import time
import re
from slackclient import SlackClient
import sqlite3
from slacker import Slacker

#instantiate Slack Client
slack_client = Slacker(SLACK_BOT_TOKEN)
#streambot user ID in slack: value assigned after bot starts up

#remember to pass in slack_bot_token before starting up or it wont work
streambot_id = None
try:
    conn = sqlite3.connect('ManageStandUp.db')
except:
    print("db stuff didnt work")

#cursor for db stuff
cursor = conn.cursor()
tableName = "ManageStandUps"
# create_table = "CREATE TABLE %s (id DATETIME,  postId text, senderId text, sender text," \
#                 "workstream text, standupUpdate text)" % (tableName)
# cursor.execute(create_table)


#Create table


#constants
RTM_READ_DELAY = 1 #time delay between reading from RTM
EXAMPLE_COMMAND = "get, update, or edit?"
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"
commands = ["get", "update", "edit"]
types = {"user": "sender", "workstream":"workstream", "update":"standupUpdate", "post":"postId"}
updates = {}
update_ids = {}
workstreams = []
users = []



#code started from https://www.fullstackpython.com/blog/build-first-slack-bot-python.html
def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            channel = event["channel"]
            user_id, message = parse_direct_mention(event["text"])
            sender_id = event["user"]
            if user_id == streambot_id:
                #determines whether event from slack is command directed at starter bot
                return (message, channel, sender_id)
            if (("stream bot".lower() in event["text"].lower()) or ("streambot".lower() in event[
                "text"].lower())):
                slack_client.api_call(
                    "chat.postMessage",
                    channel=channel,
                    text="Hello! Did you call me?")
    return (None, None, None)

def parse_direct_mention(message_text):
    """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
    """
    matches = re.search(MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    if (matches):
        return (matches.group(1), matches.group(2).strip())
    return (None, None)

def handle_command(command, channel, sender):
    default_response = "Not sure what you mean. Try *{}*".format(EXAMPLE_COMMAND)
    workstreams = list(updates.keys())

    contains_command = [x for x in commands if command.startswith(x)]

    if (len(contains_command) == 0):
        slack_client.api_call(
            "chat.postMessage",
            channel=channel,
            text=default_response
        )

    if "update" in contains_command:
        print(slack_client.api_call("users.info",user=sender))
        user_name = slack_client.api_call("users.info",user=sender)["user"]["profile"][
            "display_name"]
        sender_id = slack_client.api_call("users.info", user=sender)["user"]["id"]
        try:
            parsed_update = command.replace("update", "").split(":", 1)
            workstream = parsed_update[0].replace(" ", "").upper()
            workstreams.append(workstream.upper())
            users.append(user_name.upper())
            standup_update = parsed_update[1]
            postid = hash(standup_update)
            conn.execute("INSERT INTO {} VALUES (datetime('now'), ? , ?, ?, ? , ?)".format(tableName),
                         (postid, sender_id, user_name.upper(),
                                                workstream.upper(), standup_update ))
            slack_client.api_call(
                "chat.postMessage",
                channel=channel, link_names = 1,
                text="Updated! Post id: *"+str(postid)+"*")
        except:
            slack_client.api_call(
                "chat.postMessage",
                channel=channel, link_names = 1,
                text="Please enter a valid update command! (Hint: you might be missing a ':' "
                     "after your workstream)" )
        conn.commit()




    if "get" in contains_command:
        try:
            type = command.split(" ")[1]
            specific = command.split(" ")[2]
            if (not(type in types.keys())):
                slack_client.api_call(
                    "chat.postMessage",
                    channel=channel, link_names = 1,
                    text="I don't know what you want me to get... :( " )
            else:
                pre_count = "SELECT * FROM {} LIMIT 1".format(tableName)
                cursor.execute(pre_count)
                rows = cursor.fetchall()
                if(len(rows) == 0) :
                    response = "No updated workstreams."
                    slack_client.api_call(
                        "chat.postMessage",
                        channel=channel,
                        text=response or default_response)
                else:
                    cursor.execute("SELECT * FROM {0} where {1} = ? ".format(tableName, types[type]),
                                   (specific.upper(),))
                    if type == "workstream":
                        return_update = "*" + specific.upper() + "* updates: \n"
                        rows = cursor.fetchall()
                        for row in rows:
                            return_update += "%s <@%s> : %s \n" %(row[0], row[2], row[5])
                        print(row)
                    else:
                        return_update = "Updates from " + specific.upper() + ": \n"
                        rows = cursor.fetchall()
                        for row in rows:
                            return_update += "%s <@%s> *%s*: %s \n" %(row[0], row[2], row[4],
                                                                      row[5])
                            print(row)
                    print("return update ", return_update)
                    slack_client.api_call(
                        "chat.postMessage",
                        channel=channel, link_names = 1,
                        text=return_update )
        except:
            slack_client.api_call(
                "chat.postMessage",
                channel=channel, link_names = 1,
                text="Plz enter valid request >:(" )

    if "edit" in contains_command:
        parsed_update = command.split(" ")
        id = parsed_update[1]

        cursor.execute("SELECT * FROM {} where postId = ? ".format(tableName),
                       (id,))
        rows = cursor.fetchall()

        new_update = command.split(" ", 2)[2]
        if (len(rows) == 0):
            slack_client.api_call(
                "chat.postMessage",
                channel=channel,
                text="No post matches that ID, try again.")
        else:
            cursor.execute("UPDATE {} SET standupUpdate = ? WHERE postId = ? ".format(tableName),
                           (new_update, id))


if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Stream Bot connected and running!")
        #Read bot's user ID by calling Web API method 'auth.test'
        streambot_id = slack_client.api_call("auth.test")["user_id"]
        #storing the ID will help the bot understand if someone mentioned
        token = "xoxo-89234987234987234798098"
        while True:
            '''infinite loop, each time the loop runs, the client receieves
                any events that arrived from the Slack's RTM API'''
            command, channel, sender = parse_bot_commands(slack_client.rtm_read())
            #parse_bot_commands function determines if event contains command
            if command:
                handle_command(command, channel, sender)
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed.")
    
