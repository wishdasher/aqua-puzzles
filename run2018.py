from flask import Flask, request, redirect, Response
from pymongo import MongoClient
import twilio.twiml
import re
import datetime

app = Flask(__name__)

team_names = {}

NUM_PUZZLES = 9

# Enter the answer to the puzzle. No whitespace allowed
answers = {
    "1": "SEAM",
    "2": "1984",
    "3": "AMBIANCE",
    "4": "CLINIC",
    "5": "SUMMERDAY",
    "6": "ELEVATORS",
    "7": "VASES",
    "8": "PAYDAY",
    "9": "BEAVER",
    "META": "HARMONIZING"
}

# Enter the flavor text given for a correct answer
storyline = (
    "By the way, R1=13",
    "By the way, R2=19",
    "By the way, R3=25",
    "By the way, W1=38",
    "By the way, W2=8",
    "By the way, W3=18",
    "By the way, B1=26",
    "By the way, B2=0"
)

client = MongoClient()
db = client.devPuzzleA
teams = db.teams
subans = db.subans

stock_messages = {
    "Welcome": "Hello, thank you for contacting the IHTFP archipelago radio tower, {team_name}! Start texting us with answers [ISLAND NO.] [SOLUTION], like '1 wombat'",
    "Help": "Text [ISLAND NO.] [SOLUTION], like '1 wombat', and we'll let you know if you are correct! If you need more help, find a sherpa wearing a hat or bandana",
    "Name Already Taken": "Sorry, the name '{team_name_new}' is already taken. Text 'yes' to accept the name '{team_name_temp}' or text to create a new one",
    "Name Already Taken First": "Sorry, the name '{team_name_new}' is already taken. Text to create a new one",
    "Name Too Long": "Sorry, please keep your name under 30 characters. Text 'yes' to accept the name '{team_name_temp}' or text to create a new one",
    "Text Way Too Long": "Sorry, but you're wasting our valuable radio time, please refrain from sending such spurious messages. Shut up.",
    "Name Too Long First": "Sorry, please keep your name under 30 characters. Text to create a new one",
    "Confirm Name": "Text 'yes' to accept the name '{team_name_temp}' or text to create a new one",
    "Parse Error": "I'm sorry, we didn't understand '{text}'. Please text answers in the format [ISLAND NO.] [SOLUTION], like '1 wombat'",
    "Problem Not Exists": "There is no island no. {puzzle_number}...",
    "Correct": "Thanks! With your answer {answer} you have bottled the essence of island no. {puzzle_number}! {storyline}",
    "Incorrect": "Sorry, your answer {answer} for island no. {puzzle_number} was incorrect. Please try again.",
    "Already Answered": "You've already bottled the essence of island no. {puzzle_number}",
    "Final Puzzle": "Hi, it's the IHTFP radio tower contacting island no. {puzzle_number}. {answer} was correct. The last hint is B3=26, and congratulations on completing all of the islands, {team_name}!",
    "Meta Correct": "Congratulations {team_name}, {answer} was correct! Quickly, chase down the lead sherpa with the hat to tell them of your success.",
    "Meta Answered": "What are you doing using our twilio credit? Hurry up and chase down the sherpa with the hat!",
    "Meta Incorrect": "Sorry, {answer} was wrong. Please try again."
}

special_messages = {
    "4": {
        "HEALTH KIOSK": "Sorry, HEALTH KIOSK is on the right track but not the final answer. Look at the puzzle again.",
        "HEALTHKIOSK": "Sorry, HEALTH KIOSK is on the right track but not the final answer. Look at the puzzle again.",
    },
    "1": {
        "DIAGONAL": "DIAGONAL is right, but not the final answer. Look at the puzzle again."
    },
    "9": {
        "MITMASCOT": "MITMASCOT is not the final answer. Keep thinking.",
        "MIT MASCOT": "MIT MASCOT is not the final answer. Keep thinking.",
        "TIM": "TIM is the MIT mascot, but what kind of animal is he?"
    },
    "7": {
        "ALKALI": "ALKALI is not the final answer. Look at the puzzle again.",
        "NOBLEGASES": "NOBLEGASES is a clue. Look at the puzzle again."
    }
}

parse_length = len(stock_messages["Parse Error"].format(text=""))
name_length = len(stock_messages["Welcome"].format(team_name=""))
reDigits = re.compile(r"^\d+$")
reEndWhitespace = re.compile(r"\s+$")
reBeginWhitespace = re.compile(r"^\s+")
reWhitespace = re.compile(r"\s+")

def parse_error(command):
    if len(command) + parse_length < 160:
        return stock_messages["Parse Error"].format(text=command)
    else:
        return stock_messages["Parse Error"].format(text=(command[:160-parse_length-4] + " ..."))
        
def parse_puzzle_answers(team,from_number,root,leaf):
    if root in answers:
        if root in team[u'Correct']:
            return stock_messages["Already Answered"].format(puzzle_number=root)
        elif leaf == answers[root].upper():
            teams.update({"Number":from_number},{"$push":{"Correct":root},"$set":{"SolveTimes."+root:datetime.datetime.utcnow()}})
            subans.update({"_Puzzle":root},{"$inc":{leaf:1},"$addToSet":{"_Answers":leaf}},True)
        
            if len(team[u'Correct']) >= NUM_PUZZLES - 1:
                return stock_messages["Final Puzzle"].format(puzzle_number=root, answer=leaf, team_name=team[u'Name'])
            else:
                return stock_messages["Correct"].format(puzzle_number=root, answer=leaf, storyline=storyline[len(team[u'Correct'])])
        elif root in special_messages and leaf in special_messages[root]:
            subans.update({"_Puzzle":root},{"$inc":{leaf:1},"$addToSet":{"_Answers":leaf}},True)
            return special_messages[root][leaf]
        else:
            subans.update({"_Puzzle":root},{"$inc":{leaf:1},"$addToSet":{"_Answers":leaf}},True)
            return stock_messages["Incorrect"].format(puzzle_number=root, answer=leaf)
    else:
        return stock_messages["Problem Not Exists"].format(puzzle_number=root)
        
@app.route("/answers.txt")
def show_answers():
    ret = ""
    for ans in subans.find():
        ret += ans[u'_Puzzle'] + "\r\n"
        ret += "\r\n".join(['"{}",{}'.format(k,ans[k]) for k in ans[u'_Answers']])
        ret += "\r\n"
    
    return Response(ret, mimetype='text/plain')

@app.route("/solvedpuzzles.txt")
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
        ret += str(i) + ": " + str(puzzles_solved[i]) + "\r\n"
        
    ret += "META: " + str(puzzles_solved[NUM_PUZZLES])
    
    return Response(ret, mimetype='text/plain')

@app.route("/allteams.txt")
def show_teams():
    ret = ""
    for team in teams.find():
        ret += '"' + team[u'TempName'] + '",' + ",".join(team[u'Correct']) + "\r\n"
    return Response(ret, mimetype='text/plain')

@app.route("/", methods=['GET', 'POST'])
def hello_monkey():
    
    from_number = request.values.get('From', None)
    command = reBeginWhitespace.sub('', reEndWhitespace.sub('', request.values.get('Body', None)))
    
    tokens = command.split(None, 1)
    
    team = teams.find_one({"Number":from_number})
    
    message = parse_error(command)

    if len(command) > 101:
        message = stock_messages["Text Way Too Long"]
    elif team == None:
        if len(command) < 31:
            if teams.find_one({"$or":[{"Name":command}, {"TempName":command}]}) == None:
                message = stock_messages["Confirm Name"].format(team_name_temp=command)
                teams.insert({"Number":from_number,"TempName":command,"Correct":list()})
            else:
                message = stock_messages["Name Already Taken First"].format(team_name_new=command)
        else:
            message = stock_messages["Name Too Long First"]
    elif "Name" not in team:
        if tokens[0].upper() == 'YES':
            teams.update({"Number":from_number},{"$set":{"Name":team[u'TempName']}})
            message = stock_messages["Welcome"].format(team_name=team[u'TempName'])
        elif len(command) < 31:
            if teams.find_one({"$or":[{"Name":command}, {"TempName":command}]}) == None:
                teams.update({"Number":from_number},{"$set":{"TempName":command}})
                message = stock_messages["Confirm Name"].format(team_name_temp=command)
            else:
                message = stock_messages["Name Already Taken"].format(team_name_new=command,team_name_temp=team[u'TempName'])
        else:
            message = stock_messages["Name Too Long"].format(team_name_temp=team[u'TempName'])
    elif len(tokens) == 2:
        root,leaf = tokens
        if reDigits.search(root) != None:
            message = parse_puzzle_answers(team, from_number, root, reWhitespace.sub('',leaf).upper())
        elif root.upper() == "META":
            if "META" in team[u'Correct']:
                message = stock_messages["Meta Answered"]
            else:
                if reWhitespace.sub('',leaf).upper() == answers["META"].upper():
                    message = stock_messages["Meta Correct"].format(answer=reWhitespace.sub('',leaf).upper(), team_name=team[u'Name'])
                    teams.update({"Number":from_number},{"$push":{"Correct":root.upper()},"$set":{"SolveTimes.META":datetime.datetime.utcnow()}})
                    subans.update({"_Puzzle":"META"},{"$inc":{leaf:1},"$addToSet":{"_Answers":leaf}},True)
                else:
                    message = stock_messages["Meta Incorrect"].format(answer=reWhitespace.sub('',leaf).upper())
                    subans.update({"_Puzzle":"META"},{"$inc":{leaf:1},"$addToSet":{"_Answers":leaf}},True)
        elif root.upper() == "PENCIL-REMOVE-TEAM":
            teams.remove({"Name":leaf})
            message = "Removed " + leaf
            
    elif len(tokens) == 1:
        root = tokens[0]
        if root.upper() == "?":
            message = stock_messages["Help"]
    
    resp = twilio.twiml.Response()
    resp.sms(message)
        
    return str(resp)

if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)

    
    
    
    
