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

app = Flask(__name__, static_url_path='')
cors = CORS(app)

# Listens on port: graduation year of current freshman class
port = datetime.date.today().year + 4

team_names = {}

NUM_PUZZLES = 9

# Enter the answer to the puzzle. No whitespace allowed
answers = {
    "1": "BELIEF",
    "2": "TOTEMS",
    "3": "AIRBORNE",
    "4": "ORACLE",
    "5": "CONSCIOUS",
    "6": "SIMPLEIDEA",
    "7": "TAU",
    "8": "SOLITARY",
    "9": "REALITY",
    "META": "COLLAPSINGDREAMS"
}

# Enter the clue text given for a correct answer
storyline = {
    "1": "Belief deserves to be rewarded, your team needs a dreamy THINKER",
    "2": "Let your dreams MEANDER toward a sea of memories",
    "3": "Alas, your totem got SMASHED - how will you tell dream from reality?",
    "4": "Who knew tea BREWERS could be such cryptic oracles?",
    "5": "Your subconscious ADMIRES emotion over reason",
    "6": "A simple idea sticks, like a resilient parasite EGESTED into the brain",
    "7": "Don't think about UNICORN's. What are you thinking about?",
    "8": "Your dreams are the solitary children of an UNSOUND mind",
    "9": "IMPLANT an idea deep enough, and this dream will become your reality"
}

client = MongoClient()
db = client.splash2015
teams = db.teams
submissions = db.submissions

stock_messages = {
    "Welcome": "Welcome to the MIT Dreamscape, {team_name}! Start texting us with answers [DREAM LEVEL] [SOLUTION], like '1 inception'",
    "Help": "Text [DREAM LEVEL] [SOLUTION], like '1 inception', and we'll let you know if you are correct. If you need more help, venture down to Front Desk or find a Dream Architect wearing a top hat.",
    "Name Already Taken": "Sorry, the team name '{team_name_new}' is already taken. Text 'yes' to accept the name '{team_name_temp}' or text to create a new one.",
    "Name Already Taken First": "Sorry, the name '{team_name_new}' is already taken. Text to create a new one.",
    "Name Too Long": "Sorry, please keep your name under 30 characters. Text 'yes' to accept the name '{team_name_temp}' or text to create a new one.",
    "Text Way Too Long": "You're wasting your valuable dream time. Please refrain from sending such long-winded messages.",
    "Name Too Long First": "Sorry, please keep your name under 30 characters. Text to create a new one.",
    "Confirm Name": "Text 'yes' to accept the team name '{team_name_temp}' or text to create a new one.",
    "Parse Error": "Sorry, we didn't understand '{text}'. Please text answers in the format [DREAM LEVEL] [SOLUTION], like '1 inception'. If you need more help, venture down to Front Desk or find a Dream Architect wearing a top hat.",
    "Problem Not Exists": "There is no Dream Level {puzzle_number}...",
    "Correct": "With your answer {answer} you have discovered the secret clue hidden in Dream Level {puzzle_number}: \"{storyline}\"",
    "Incorrect": "Sorry, your answer {answer} for Dream Level {puzzle_number} was incorrect.\nPlease try again (you can also ask us for hints).",
    "Already Answered": "You've already discovered the secrets of Dream Level {puzzle_number}: \"{storyline}\"",
    "Final Puzzle": "With your answer {answer}, you've discovered the final clue hidden in Dream Level {puzzle_number}: \"{storyline}\"\nCongrats on completing all the dream levels, {team_name}!\nPlease send ONE brave team member to unlock a final secret!",
    "Meta Correct": "Congratulations {team_name}, you've discovered the secret idea: {answer}. This concludes the puzzle hunt!",
    "Meta Answered": "What are you doing wasting your valuable dream time?",
    "Meta Incorrect": "Sorry, {answer} was wrong. Please try again."
}

special_messages = {
    "1": {
        "WRONGANSWER": "WRONGANSWER is close, but not the final answer. Look at the puzzle again.",
        "INCEPTION": "Nice try, but that's not the correct answer."
    },
    "7": {
        "6.28": "Doh! And what is the symbol for 6.28?",
        "628": "Doh! And what is the symbol for 6.28?"
    }
}

parse_length = len(stock_messages["Parse Error"].format(text=""))
name_length = len(stock_messages["Welcome"].format(team_name=""))
reDigits = re.compile(r"^\d+$")
reEndWhitespace = re.compile(r"\s+$")
reBeginWhitespace = re.compile(r"^\s+")
reWhitespace = re.compile(r"\s+")

def parse_error(command):
    if len(command) + parse_length < 240:
        return stock_messages["Parse Error"].format(text=command)
    else:
        return stock_messages["Parse Error"].format(text=(command[:240-parse_length-4] + " ..."))
        
def parse_puzzle_answers(team,from_number,root,leaf):
    if root in answers:
        if root in team[u'Correct']:
            return stock_messages["Already Answered"].format(puzzle_number=root, storyline=storyline[root])
        elif leaf == answers[root].upper():
            teams.update({"Number":from_number},{"$push":{"Correct":root,"Submissions":str(root+" "+leaf)},"$set":{"SolveTimes."+root:datetime.datetime.utcnow()}})
            submissions.update({"_Puzzle":root},{"$inc":{leaf:1},"$addToSet":{"_Answers":leaf}},True)
            if len(team[u'Correct']) >= NUM_PUZZLES - 1:
                return stock_messages["Final Puzzle"].format(puzzle_number=root, answer=leaf, team_name=team[u'Name'], storyline=storyline[root])
            else:
                return stock_messages["Correct"].format(puzzle_number=root, answer=leaf, storyline=storyline[root])
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
            number = team[u'Number'][2:]
            ret += team[u'Name'] + '-(' + number[:3]+"."+number[3:6]+"."+number[6:] + ')-' + str(elapsed) + "-" + ",".join(team[u'Correct']) + "-" + str(len(team[u'Texts'])) + "\r\n"
    return Response(ret, mimetype='text/plain')

@app.route("/aguamenti/")
def root():
    return render_template("index.html")

def strip(command):
    return re.compile(r"[^\w\d\-]+").sub(" ", command)

def digitize(command):
    command = strip(command)
    words = [["one", "won"], ["t(w|o)?o"], ["three"], ["fo(u)?r"], ["five"], ["s(i|e)x"], ["seven"], ["eight", "ate"], ["nine"], ["ten"]]
    for i in range(0, len(words)):
        regex = re.compile("^("+string.join(words[i],"|")+") ", re.I)
        command = regex.sub(str(i+1)+" ", command)
    return strip(command)

@app.route("/team")
def show_team():
    name = request.values.get('Name', None)
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
            if len(command) < 31:
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
                    message = stock_messages["Meta Answered"]
                else:
                    leaf = reWhitespace.sub('',leaf).upper()
                    if leaf == answers["META"].upper():
                        message = stock_messages["Meta Correct"].format(answer=leaf, team_name=team[u'Name'])
                        teams.update({"Number":from_number},{"$push":{"Correct":root, "Submissions":str(root+" "+leaf)},"$set":{"SolveTimes.META":datetime.datetime.utcnow()}})
                        submissions.update({"_Puzzle":"META"},{"$inc":{leaf:1},"$addToSet":{"_Answers":leaf}},True)
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
            root = tokens[0]
            if root == "?":
                message = stock_messages["Help"]
        
        resp = twilio.twiml.Response()
        resp.sms(message)
            
        return str(resp)

    else:
        return render_template("index.html")


if __name__ == "__main__":
    app.run('0.0.0.0', port=port, debug=True)
