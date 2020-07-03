# Aquarium Puzzlehunt

Server for running annual MIT Aquarium Puzzlehunt 

## Editing the solutions template

The *puzzle.py* file runs the server and also contains the template messages and solutions. 
Edit the solutions, flavor texts, and storyline messages accordingly.

*Important*: When modifying the puzzle.py file for a new year, archive the previous year's puzzle file as *XXXX.py* where XXXX is the class year e.g. 2020.py for Class of 2020.

## How to setup Twilio

1. Create a [Twilio](https://www.twilio.com) account, and purchase a phone number that will receive texts (e.g. you can choose a special number like XXX-MIT-2020)

2. On the Twilio dashboard, configure incoming text messages to make POST requests to *http://[public IP]:2019*, where [public IP] is the public IP or domain name of the machine that this server will be running on.

## Starting the server

From the Terminal or Command Prompt of your server, run:

```bash
$ pip install flask mongo twilio twython -U flask-cors

$ python puzzle.py
```

## Tracking progress from web browser

- From a browser, navigate to *http://[public IP]:2019/aguamenti/* where [public IP] is the public IP or domain name of the machine that this server is running on.