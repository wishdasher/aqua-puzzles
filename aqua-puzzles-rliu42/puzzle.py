from flask import Flask, request, redirect, Response, url_for, render_template
try:
    from flask.ext.cors import CORS  # The typical way to import flask-cors
except ImportError:
    # Path hack allows examples to be run without installation.
    import os
    parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.sys.path.insert(0, parentdir)
    from flask.ext.cors import CORS
from pymongo import MongoClient
import twilio.twiml
import re
import socket
import string
import datetime
import urllib
from twython import Twython

# Twitter bot credentials
consumer_key = 'smm70Zj6BlCBwaPdHxSEWQPQE'
consumer_secret = 'xFdrtPdSafgigCpV4ocQTiWcXVIsPS6t7AYfOjjj7OjmAblzwc'
access_token = '770719816982401025-LcBA2zzibq4lZKIz9fpwxbzvOyYRcOP'
access_token_secret = 'C7uTNDPI3CJGMhdN9qf2AtodOLV0zhMzPbkOWzTXuuHQq'

# OAuth process, using the keys and tokens
tweetbot = Twython(consumer_key, consumer_secret, access_token, access_token_secret)

app = Flask(__name__, static_url_path='')
cors = CORS(app)

# Listens on port: graduation year of current freshman class
port = 2021

# EDITABLE
NUM_PUZZLES = 9

# EDITABLE: Enter the answers to each puzzle. No whitespace allowed.
answers = {
    "1": "THEORIZE",
    "2": "RUNOFF",
    "3": "ENVIES",
    "4": "NEITHER",
    "5": "THUNDERED",
    "6": "CONSERVER",
    "7": "EITHER",
    "8": "NODE",
    "9": "FORTIFY",
    "META": "THEINFINITECORRIDOR"
}

# EDITABLE (optional): Flavor text that precedes a correct response
preface = {
    "1": "",
    "2": "",
    "3": "",
    "4": "",
    "5": "",
    "6": "",
    "7": "",
    "8": "",
    "9": ""
}

# EDITABLE: Enter the clue text given for a correct answer
storyline = {
    "1": "You earned 0 points!",
    "2": "You earned 4 points!",
    "3": "You earned 7 points!",
    "4": "You earned 3 points!",
    "5": "You earned 100 points!",
    "6": "You earned 7 points!",
    "7": "You earned 3 points!",
    "8": "You earned 1 point!",
    "9": "You earned 50 points!"
}

client = MongoClient()
# IMPORTANT: Change the database each time the puzzlehunt is run
db = client.aquahunt_2017
teams = db.teams
submissions = db.submissions

# EDITABLE
twitter_messages = {
    "Team Create": "{team_name} ({from_number}) created a team! #{team_name_short}",
    "Correct": "{team_name} solved #puzzle{puzzle_number}. Total solved: {num_solved}/" + str(NUM_PUZZLES) + ". Elapsed time: {elapsed_time}. #{team_name_short}",
    "Meta Correct": "@aquapuzzles {team_name} just solved puzzle #META! Time: {time}. #runaround #{team_name_short}",
    "Final Puzzle": "@aquapuzzles {team_name} has solved all puzzles except #META #{team_name_short}"
}

# EDITABLE
stock_messages = {
    "Welcome": "Welcome to the Class of 2021 Jeopardy game, {team_name}! Start texting us with answers [QUESTION NO] [SOLUTION], like '1 fish'",
    "Help": "Text [QUESTION NO] [SOLUTION], like '1 fish', and we'll let you know if you are correct. Look for a staff member for more help.",
    "Name Already Taken": "Sorry, the team name '{team_name_new}' is already taken. Text 'yes' to accept the name '{team_name_temp}' or text to create a new one.",
    "Name Already Taken First": "Sorry, the name '{team_name_new}' is already taken. Text to create a new one.",
    "Name Too Long": "Sorry, please keep your name under 20 characters. Text 'yes' to accept the name '{team_name_temp}' or text again to create a new one.",
    "Text Way Too Long": "You're wasting my time! Please refrain from sending such long-winded messages.",
    "Name Too Long First": "Sorry, please keep your name under 20 characters. Text to create a new one.",
    "Confirm Name": "Text 'yes' to accept the team name '{team_name_temp}' or text to create a new one.",
    #"Parse Error": "Sorry, we didn't understand '{text}'. Please text answers in the format [MYSTERY CASE NO] [SOLUTION], like '1 sherlock'. If you need more help, venture down to Front Desk or find a staff member wearing a top hat.",
    "Parse Error": "Sorry, we didn't understand '{text}'. Please text answers in the format [QUESTION NO] [SOLUTION], like '1 fish'. You can also ask the teachers for hints!",
    "Problem Not Exists": "There is no Question No. {puzzle_number}...",
    "Correct": "With your solution {answer} you've solved Question {puzzle_number}: {storyline} {preface}",
    "Incorrect": "Sorry, your answer {answer} for Question {puzzle_number} was incorrect.\nPlease try again (you can also ask the staff for hints)",
    "Already Answered": "You've already solved Question {puzzle_number}: {storyline} {preface}",
    "Final Puzzle": "{preface} With your solution {answer}, you've solved Question {puzzle_number}: {storyline} Congrats on solving all the categories {team_name}! Head to front desk to receive the Final Jeopardy question now!",
    "Meta Correct": "Well done {team_name}! With your answer {answer} you've answered the Final Jeopardy question: Which hallway at MIT have students in Civil Engineering studied as a model of highway traffic? This concludes the puzzlehunt, congrats!",
    "Meta Answered": "What are you still doing wasting precious game time?",
    "Meta Incorrect": "Sorry, {answer} is incorrect. Please try again."
}

# EDITABLE: hints for common incorrect answers
special_messages = {
    "1": {
        "FISH": "Nice try, but FISH is not the correct answer. Try solving the puzzle."
    }
}

parse_length = len(stock_messages["Parse Error"].format(text=""))
name_length = len(stock_messages["Welcome"].format(team_name=""))
reDigits = re.compile(r"^\d+$")
reEndWhitespace = re.compile(r"\s+$")
reBeginWhitespace = re.compile(r"^\s+")
reWhitespace = re.compile(r"\s+|[^\w\d]+")

def parse_error(command):
    if len(command) + parse_length < 240:
        return stock_messages["Parse Error"].format(text=command)
    else:
        return stock_messages["Parse Error"].format(text=(command[:240-parse_length-4] + " ..."))

def parse_puzzle_answers(team,from_number,root,leaf):
    if root in answers:
        if root in team[u'Correct']:
            return stock_messages["Already Answered"].format(puzzle_number=root, storyline=storyline[root], preface=preface[root])
        elif leaf == answers[root].upper():
            teams.update({"Number":from_number},{"$push":{"Correct":root,"Submissions":str(root+" "+leaf)},"$set":{"SolveTimes."+root:datetime.datetime.utcnow()}})
            submissions.update({"_Puzzle":root},{"$inc":{leaf:1},"$addToSet":{"_Answers":leaf}},True)
            num_solved = len(team[u'Correct']) + 1
            if num_solved >= NUM_PUZZLES and u'META' not in team[u'SolveTimes']:
                tweetbot.update_status(status=twitter_messages["Final Puzzle"].format(team_name=team[u'Name'],team_name_short=reWhitespace.sub('',team[u'Name'])))
                return stock_messages["Final Puzzle"].format(puzzle_number=root, answer=leaf, team_name=team[u'Name'], storyline=storyline[root], preface=preface[root])
            else:
                delta = datetime.datetime.utcnow() - team[u'SolveTimes'][u'START']
                mins, secs = divmod(delta.days*86400 + delta.seconds, 60)
                elapsed_time = str(mins) + "m, " + str(secs) + "s"
                tweetbot.update_status(status=twitter_messages["Correct"].format(team_name=team[u'Name'],puzzle_number=root,num_solved=num_solved,elapsed_time=elapsed_time,team_name_short=reWhitespace.sub('',team[u'Name'])))
                return stock_messages["Correct"].format(puzzle_number=root, answer=leaf, storyline=storyline[root], preface=preface[root])
        elif root in special_messages and leaf in special_messages[root]:
            submissions.update({"_Puzzle":root},{"$inc":{leaf:1},"$addToSet":{"_Answers":leaf}},True)
            teams.update({"Number":from_number},{"$push":{"Submissions":str(root+" "+leaf)}})
            return special_messages[root][leaf]
        else:
            submissions.update({"_Puzzle":root},{"$inc":{leaf:1},"$addToSet":{"_Answers":leaf}},True)
            teams.update({"Number":from_number},{"$push":{"Submissions":str(root+" "+leaf)}})
            return stock_messages["Incorrect"].format(puzzle_number=root, answer=leaf)
    else:
        return stock_messages["Problem Not Exists"].format(puzzle_number=root)

@app.route("/data")
def show_data():
    ret = ""
    for team in teams.find():
        ret += str(team) + "\r\n\r\n"

    return Response(ret, mimetype='text/plain')

@app.route("/answers")
def show_answers():
    ret = ""
    for ans in submissions.find():
        ret += ans[u'_Puzzle'] + "\r\n"
        ret += "\r\n".join(['{}({}) '.format(k.upper(),ans[k]) for k in ans[u'_Answers']])
        ret += "\r\n"

    return Response(ret, mimetype='text/plain')

@app.route("/solved")
def show_stats():
    total_solved = [0] * (NUM_PUZZLES + 2)
    puzzles_solved = [0] * (NUM_PUZZLES + 1)
    for team in teams.find():
        for i in range(NUM_PUZZLES + 2):
            if len(team[u'Correct']) == i:
                total_solved[i] += 1
        for i in range(NUM_PUZZLES):
            if str(i+1) in team[u'Correct']:
                puzzles_solved[i] += 1
        if "META" in team[u'Correct']:
            puzzles_solved[NUM_PUZZLES] += 1

    ret = "# of Teams by total # of problems solved:\r\n"
    for i in range(NUM_PUZZLES + 2):
        ret += str(i) + ": " + str(total_solved[i]) + "\r\n"

    ret += "\r\n# of puzzle solves by puzzle:\r\n"
    for i in range(NUM_PUZZLES):
        ret += str(i+1) + ": " + str(puzzles_solved[i]) + "\r\n"

    ret += "META: " + str(puzzles_solved[NUM_PUZZLES])

    return Response(ret, mimetype='text/plain')

@app.route("/teams")
def show_teams():
    ret = ""
    for team in teams.find():
        if "Name" in team:
            if u'META' in team[u'SolveTimes'] and (datetime.datetime.utcnow() - team[u'SolveTimes'][u'START']).days==0:
                delta = team[u'SolveTimes'][u'META'] - team[u'SolveTimes'][u'START']
            else:
                delta = datetime.datetime.utcnow() - team[u'SolveTimes'][u'START']
            mins, secs = divmod(delta.days*86400 + delta.seconds, 60)
            if secs < 10:
                secs = "0" + str(secs)
            elapsed = str(mins) + "." + str(secs)
            number = team[u'Number']
            if number[0] == "+":
                # phone number - strip leading +1
                number = number[2:]
                number = number[:3]+"."+number[3:6]+"."+number[6:]
            ret += team[u'Name'] + '~(' + number + ')~' + elapsed + "~" + ",".join(team[u'Correct']) + "~" + str(len(team[u'Texts'])) + "\r\n"
    return Response(ret, mimetype='text/plain')

@app.route("/aguamenti/")
def root():
    return render_template("index.html")

def strip(command):
    return re.compile(r"[^\w\d]+").sub(" ", command)

def digitize(command):
    command = strip(command)
    words = [["one", "won"], ["t(w|o)?o"], ["three"], ["fo(u)?r"], ["five"], ["s(i|e)x"], ["seven"], ["eight", "ate"], ["nine"], ["ten"]]
    for i in range(0, len(words)):
        regex = re.compile("^("+string.join(words[i],"|")+") ", re.I)
        command = regex.sub(str(i+1)+" ", command)
    return strip(command)

@app.route("/team")
def show_team():
    name = urllib.unquote(request.values.get('Name', None))
    team = teams.find_one({"Name":name})
    ret = ""
    if not team is None:
        number = team[u'Number'][2:]
        ret += "<style>body{font-family: 'Courier'}</style> <br>Team <b>" + team[u'Name'] + "</b><br>"
        ret += "<a href='sms:" + number + "'>TEXT " + number[:3]+"."+number[3:6]+"."+number[6:] + "</a><br>"
        ret += "<a href='tel:" + number + "'>CALL " + number[:3]+"."+number[3:6]+"."+number[6:] + "</a>" + "<br><br><b>Submissions</b>"
        for submission in team[u'Submissions']:
            tokens = submission.split(None, 1)
            if len(tokens) == 2:
                root, leaf = tokens
                if answers[root.upper()].upper() == leaf:
                    ret += "<br> <span style='color:green'><b>" + root + "</b> " + leaf + "</span>"
                else:
                    ret += "<br> <span style='color:red'><b>" + root + "</b> " + leaf + "</span>"
            else:
                ret += "<br> <span style='color:red'>" + submission + "</span>"
    return Response(ret, mimetype='text/html')

@app.route("/puzzle")
def show_puzzle():
    puzzle = request.values.get('id', None)
    answers = submissions.find_one({"_Puzzle":puzzle})
    ret = "<style>body{font-family:'Courier'}</style><br><b>Puzzle " + puzzle + "</b><br><br><b>Submissions</b><br>"
    if not answers is None:
        ret += "<br>".join(['<b>{}</b> ({})'.format(k,answers[k]) for k in answers[u'_Answers']])
    return Response(ret, mimetype='text/html')


@app.route("/", methods=['GET', 'POST'])
def hello_monkey():

    from_number = request.values.get('From', None)
    team = teams.find_one({"Number":from_number})

    if from_number != None:
        command = reBeginWhitespace.sub('', reEndWhitespace.sub('', request.values.get('Body', None)))
        tokens = digitize(command).split(None, 1)
        message = parse_error(command)
        if team != None:
            teams.update({"Number":from_number},{"$push":{"Texts":command}})
        if len(command) > 101:
            message = stock_messages["Text Way Too Long"]
        elif team == None:
            if len(command) < 21:
                command = command.upper()
                if teams.find_one({"$or":[{"Name":command}, {"TempName":command}]}) == None:
                    message = stock_messages["Confirm Name"].format(team_name_temp=command)
                    teams.insert({"Number":from_number,"TempName":command,"Correct":list(),"Submissions":list(),"Texts":list()})
                else:
                    message = stock_messages["Name Already Taken First"].format(team_name_new=command)
            else:
                message = stock_messages["Name Too Long First"]
        elif "Name" not in team:
            if tokens[0].upper() == 'YES':
                teams.update({"Number":from_number},{"$set":{"Name":team[u'TempName']}})
                teams.update({"Number":from_number},{"$set":{"SolveTimes.START":datetime.datetime.utcnow()}})
                tweetbot.update_status(status=twitter_messages["Team Create"].format(team_name=team[u'TempName'],from_number=from_number,team_name_short=reWhitespace.sub('',team[u'TempName'])))
                message = stock_messages["Welcome"].format(team_name=team[u'TempName'])
            elif len(command) < 31:
                command = command.upper()
                if teams.find_one({"$or":[{"Name":command}, {"TempName":command}]}) == None:
                    teams.update({"Number":from_number},{"$set":{"TempName":command}})
                    message = stock_messages["Confirm Name"].format(team_name_temp=command)
                else:
                    message = stock_messages["Name Already Taken"].format(team_name_new=command,team_name_temp=team[u'TempName'])
            else:
                message = stock_messages["Name Too Long"].format(team_name_temp=team[u'TempName'])
        elif len(tokens) == 2:
            root, leaf = tokens
            root = root.upper()
            if reDigits.search(root) != None:
                message = parse_puzzle_answers(team, from_number, root, reWhitespace.sub('',leaf).upper())
            elif root == "META":
                if "META" in team[u'Correct']:
                    message = stock_messages["Meta Correct"].format(answer=leaf, team_name=team[u'Name'])
                else:
                    leaf = reWhitespace.sub('',leaf).upper()
                    if leaf == answers["META"].upper():
                        message = stock_messages["Meta Correct"].format(answer=leaf, team_name=team[u'Name'])
                        teams.update({"Number":from_number},{"$push":{"Correct":root, "Submissions":str(root+" "+leaf)},"$set":{"SolveTimes.META":datetime.datetime.utcnow()}})
                        submissions.update({"_Puzzle":"META"},{"$inc":{leaf:1},"$addToSet":{"_Answers":leaf}},True)
                        delta = datetime.datetime.utcnow() - team[u'SolveTimes'][u'START']
                        mins, secs = divmod(delta.days*86400 + delta.seconds, 60)
                        elapsed_time = str(mins) + "m, " + str(secs) + "s"
                        tweetbot.update_status(status=twitter_messages["Meta Correct"].format(team_name=team[u'Name'], time=elapsed_time, team_name_short=reWhitespace.sub('',team[u'Name'])))
                    else:
                        message = stock_messages["Meta Incorrect"].format(answer=leaf)
                        submissions.update({"_Puzzle":"META"},{"$inc":{leaf:1},"$addToSet":{"_Answers":leaf}},True)
            elif root == "REMOVETEAM":
                leaf = leaf.upper()
                teams.remove({"Name":leaf})
                teams.remove({"TempName":leaf})
                message = "Removed " + leaf
            elif root == "CLEAR":
                if leaf.upper() == "SUBMISSIONS":
                    db.submissions.remove()
                    message = "Cleared submissions"

        elif len(tokens) == 1:
            root = tokens[0].upper()
            if root == "?" or root == "HELP":
                message = stock_messages["Help"]

        resp = twilio.twiml.Response()
        resp.sms(message)

        return str(resp)

    else:
        return render_template("index.html")


if __name__ == "__main__":
    app.run('0.0.0.0', port=port, debug=True)
